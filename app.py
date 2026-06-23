import os
import secrets
import string
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'platform.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Affiliate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='approved')  # approved, pending, suspended
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    links = db.relationship('TrackingLink', backref='affiliate', lazy=True)
    payout_requests = db.relationship('PayoutRequest', backref='affiliate', lazy=True)

    def balance(self):
        """Approved, unpaid conversion earnings minus paid-out / pending payouts."""
        earned = sum(
            c.commission_amount for c in Conversion.query
            .join(TrackingLink)
            .filter(TrackingLink.affiliate_id == self.id, Conversion.status == 'approved')
            .all()
        )
        paid_or_pending = sum(
            p.amount for p in self.payout_requests if p.status in ('pending', 'paid')
        )
        return round(earned - paid_or_pending, 2)

    def total_earned(self):
        return round(sum(
            c.commission_amount for c in Conversion.query
            .join(TrackingLink)
            .filter(TrackingLink.affiliate_id == self.id, Conversion.status == 'approved')
            .all()
        ), 2)


class Advertiser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    website = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    offers = db.relationship('Offer', backref='advertiser', lazy=True)


class Offer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    advertiser_id = db.Column(db.Integer, db.ForeignKey('advertiser.id'), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    destination_url = db.Column(db.String(500), nullable=False)
    commission_type = db.Column(db.String(20), default='percent')  # percent or fixed
    commission_value = db.Column(db.Float, nullable=False)  # percent (e.g. 10) or fixed dollars
    payout_value = db.Column(db.Float, default=100.0)  # assumed sale value for percent calc demo
    status = db.Column(db.String(20), default='active')  # active, paused
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    links = db.relationship('TrackingLink', backref='offer', lazy=True)

    def commission_label(self):
        if self.commission_type == 'percent':
            return f"{self.commission_value:g}% per sale"
        return f"${self.commission_value:,.2f} per conversion"


class TrackingLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    affiliate_id = db.Column(db.Integer, db.ForeignKey('affiliate.id'), nullable=False)
    offer_id = db.Column(db.Integer, db.ForeignKey('offer.id'), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    clicks = db.relationship('Click', backref='link', lazy=True)
    conversions = db.relationship('Conversion', backref='link', lazy=True)

    def click_count(self):
        return len(self.clicks)

    def conversion_count(self):
        return len(self.conversions)

    def conversion_rate(self):
        c = self.click_count()
        return round((self.conversion_count() / c) * 100, 1) if c else 0.0


class Click(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey('tracking_link.id'), nullable=False)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Conversion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey('tracking_link.id'), nullable=False)
    order_value = db.Column(db.Float, nullable=False)
    commission_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='approved')  # approved, reversed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class PayoutRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    affiliate_id = db.Column(db.Integer, db.ForeignKey('affiliate.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid, rejected
    requested_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gen_code(length=8):
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def login_required_affiliate(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'affiliate_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def login_required_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin login required.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper


def current_affiliate():
    aid = session.get('affiliate_id')
    return Affiliate.query.get(aid) if aid else None


# ---------------------------------------------------------------------------
# Public / marketing routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if current_affiliate():
        return redirect(url_for('dashboard'))
    offer_count = Offer.query.filter_by(status='active').count()
    affiliate_count = Affiliate.query.count()
    return render_template('index.html', offer_count=offer_count, affiliate_count=affiliate_count)


# ---------------------------------------------------------------------------
# Affiliate auth
# ---------------------------------------------------------------------------

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_affiliate():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('signup.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('signup.html')
        if Affiliate.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return render_template('signup.html')

        affiliate = Affiliate(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(affiliate)
        db.session.commit()

        session['affiliate_id'] = affiliate.id
        flash('Account created. Welcome aboard!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_affiliate():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        affiliate = Affiliate.query.filter_by(email=email).first()

        if affiliate and check_password_hash(affiliate.password_hash, password):
            if affiliate.status == 'suspended':
                flash('This account has been suspended. Contact support.', 'error')
                return render_template('login.html')
            session['affiliate_id'] = affiliate.id
            return redirect(url_for('dashboard'))

        flash('Incorrect email or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('affiliate_id', None)
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Affiliate dashboard
# ---------------------------------------------------------------------------

@app.route('/dashboard')
@login_required_affiliate
def dashboard():
    affiliate = current_affiliate()
    links = TrackingLink.query.filter_by(affiliate_id=affiliate.id).all()

    total_clicks = sum(l.click_count() for l in links)
    total_conversions = sum(l.conversion_count() for l in links)

    recent_conversions = (
        Conversion.query.join(TrackingLink)
        .filter(TrackingLink.affiliate_id == affiliate.id)
        .order_by(Conversion.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        'dashboard.html',
        affiliate=affiliate,
        links=links,
        total_clicks=total_clicks,
        total_conversions=total_conversions,
        recent_conversions=recent_conversions,
    )


@app.route('/offers')
@login_required_affiliate
def offers():
    affiliate = current_affiliate()
    all_offers = Offer.query.filter_by(status='active').all()
    my_links = {l.offer_id: l for l in TrackingLink.query.filter_by(affiliate_id=affiliate.id).all()}
    return render_template('offers.html', affiliate=affiliate, offers=all_offers, my_links=my_links, base_url=request.host_url.rstrip('/'))


@app.route('/offers/<int:offer_id>/get-link', methods=['POST'])
@login_required_affiliate
def get_link(offer_id):
    affiliate = current_affiliate()
    offer = Offer.query.get_or_404(offer_id)

    existing = TrackingLink.query.filter_by(affiliate_id=affiliate.id, offer_id=offer.id).first()
    if existing:
        flash('You already have a link for this offer.', 'info')
        return redirect(url_for('offers'))

    code = gen_code()
    while TrackingLink.query.filter_by(code=code).first():
        code = gen_code()

    link = TrackingLink(affiliate_id=affiliate.id, offer_id=offer.id, code=code)
    db.session.add(link)
    db.session.commit()

    flash(f'Tracking link generated for {offer.name}.', 'success')
    return redirect(url_for('offers'))


@app.route('/links')
@login_required_affiliate
def links():
    affiliate = current_affiliate()
    my_links = TrackingLink.query.filter_by(affiliate_id=affiliate.id).all()
    return render_template('links.html', affiliate=affiliate, links=my_links, base_url=request.host_url.rstrip('/'))


@app.route('/payouts', methods=['GET', 'POST'])
@login_required_affiliate
def payouts():
    affiliate = current_affiliate()

    if request.method == 'POST':
        try:
            amount = round(float(request.form.get('amount', 0)), 2)
        except ValueError:
            amount = 0

        balance = affiliate.balance()
        if amount <= 0:
            flash('Enter a valid payout amount.', 'error')
        elif amount > balance:
            flash(f'You can request up to ${balance:,.2f}.', 'error')
        else:
            req = PayoutRequest(affiliate_id=affiliate.id, amount=amount)
            db.session.add(req)
            db.session.commit()
            flash('Payout requested. Admin will review it shortly.', 'success')
        return redirect(url_for('payouts'))

    history = PayoutRequest.query.filter_by(affiliate_id=affiliate.id).order_by(PayoutRequest.requested_at.desc()).all()
    return render_template('payouts.html', affiliate=affiliate, history=history)


# ---------------------------------------------------------------------------
# Tracking: click redirect + conversion postback (simulated merchant callback)
# ---------------------------------------------------------------------------

@app.route('/go/<code>')
def track_click(code):
    link = TrackingLink.query.filter_by(code=code).first()
    if not link:
        abort(404)

    click = Click(
        link_id=link.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:255],
    )
    db.session.add(click)
    db.session.commit()

    session['click_code'] = code  # used by the simulated "conversion" demo button
    separator = '&' if '?' in link.offer.destination_url else '?'
    return redirect(f"{link.offer.destination_url}{separator}ref={code}")


@app.route('/simulate-conversion', methods=['GET', 'POST'])
def simulate_conversion():
    """
    Stand-in for a merchant's postback/webhook that would normally fire
    server-to-server when a real purchase completes. Lets you demo the
    full click -> conversion -> commission -> payout loop without a
    real merchant integration.
    """
    code = request.values.get('code') or session.get('click_code')
    link = TrackingLink.query.filter_by(code=code).first() if code else None

    if request.method == 'POST':
        if not link:
            flash('No tracking code found. Click an affiliate link first.', 'error')
            return redirect(url_for('simulate_conversion'))

        try:
            order_value = round(float(request.form.get('order_value', 0)), 2)
        except ValueError:
            order_value = 0

        offer = link.offer
        if offer.commission_type == 'percent':
            commission = round(order_value * (offer.commission_value / 100), 2)
        else:
            commission = round(offer.commission_value, 2)

        conv = Conversion(link_id=link.id, order_value=order_value, commission_amount=commission)
        db.session.add(conv)
        db.session.commit()

        flash(f'Conversion recorded — ${commission:,.2f} commission credited to the affiliate.', 'success')
        return redirect(url_for('simulate_conversion'))

    return render_template('simulate_conversion.html', link=link)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        admin = Admin.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_id'] = admin.id
            return redirect(url_for('admin_dashboard'))
        flash('Incorrect admin credentials.', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('index'))


@app.route('/admin')
@login_required_admin
def admin_dashboard():
    stats = {
        'affiliates': Affiliate.query.count(),
        'advertisers': Advertiser.query.count(),
        'offers': Offer.query.filter_by(status='active').count(),
        'clicks': Click.query.count(),
        'conversions': Conversion.query.count(),
        'pending_payouts': PayoutRequest.query.filter_by(status='pending').count(),
    }
    return render_template('admin_dashboard.html', stats=stats)


@app.route('/admin/advertisers', methods=['GET', 'POST'])
@login_required_admin
def admin_advertisers():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        website = request.form.get('website', '').strip()
        if name:
            db.session.add(Advertiser(name=name, website=website))
            db.session.commit()
            flash('Advertiser added.', 'success')
        return redirect(url_for('admin_advertisers'))

    advertisers = Advertiser.query.all()
    return render_template('admin_advertisers.html', advertisers=advertisers)


@app.route('/admin/offers', methods=['GET', 'POST'])
@login_required_admin
def admin_offers():
    if request.method == 'POST':
        try:
            advertiser_id = int(request.form.get('advertiser_id'))
            commission_value = float(request.form.get('commission_value', 0))
        except (TypeError, ValueError):
            flash('Invalid offer data.', 'error')
            return redirect(url_for('admin_offers'))

        offer = Offer(
            advertiser_id=advertiser_id,
            name=request.form.get('name', '').strip(),
            description=request.form.get('description', '').strip(),
            destination_url=request.form.get('destination_url', '').strip(),
            commission_type=request.form.get('commission_type', 'percent'),
            commission_value=commission_value,
        )
        db.session.add(offer)
        db.session.commit()
        flash('Offer created.', 'success')
        return redirect(url_for('admin_offers'))

    offers_list = Offer.query.order_by(Offer.created_at.desc()).all()
    advertisers = Advertiser.query.all()
    return render_template('admin_offers.html', offers=offers_list, advertisers=advertisers)


@app.route('/admin/offers/<int:offer_id>/toggle', methods=['POST'])
@login_required_admin
def admin_toggle_offer(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    offer.status = 'paused' if offer.status == 'active' else 'active'
    db.session.commit()
    return redirect(url_for('admin_offers'))


@app.route('/admin/affiliates')
@login_required_admin
def admin_affiliates():
    affiliates = Affiliate.query.order_by(Affiliate.created_at.desc()).all()
    return render_template('admin_affiliates.html', affiliates=affiliates)


@app.route('/admin/affiliates/<int:affiliate_id>/toggle-suspend', methods=['POST'])
@login_required_admin
def admin_toggle_affiliate(affiliate_id):
    affiliate = Affiliate.query.get_or_404(affiliate_id)
    affiliate.status = 'suspended' if affiliate.status != 'suspended' else 'approved'
    db.session.commit()
    return redirect(url_for('admin_affiliates'))


@app.route('/admin/payouts', methods=['GET', 'POST'])
@login_required_admin
def admin_payouts():
    if request.method == 'POST':
        payout_id = request.form.get('payout_id')
        action = request.form.get('action')
        payout = PayoutRequest.query.get_or_404(payout_id)
        if action in ('paid', 'rejected'):
            payout.status = action
            payout.resolved_at = datetime.now(timezone.utc)
            db.session.commit()
            flash(f'Payout marked {action}.', 'success')
        return redirect(url_for('admin_payouts'))

    pending = PayoutRequest.query.filter_by(status='pending').order_by(PayoutRequest.requested_at).all()
    resolved = PayoutRequest.query.filter(PayoutRequest.status != 'pending').order_by(PayoutRequest.resolved_at.desc()).limit(20).all()
    return render_template('admin_payouts.html', pending=pending, resolved=resolved)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def seed_data():
    if Admin.query.first() is None:
        db.session.add(Admin(email='admin@platform.com', password_hash=generate_password_hash('admin1234')))

    if Advertiser.query.first() is None:
        adv1 = Advertiser(name='Northwind Outdoor Gear', website='https://example-northwind.com')
        adv2 = Advertiser(name='Lumen Software', website='https://example-lumen.com')
        adv3 = Advertiser(name='Verde Skincare', website='https://example-verde.com')
        db.session.add_all([adv1, adv2, adv3])
        db.session.flush()

        db.session.add_all([
            Offer(advertiser_id=adv1.id, name='Trailblazer Backpack 30L', destination_url='https://example-northwind.com/products/trailblazer-30l', commission_type='percent', commission_value=12, description='Lightweight hiking backpack, our best-selling SKU.'),
            Offer(advertiser_id=adv2.id, name='Lumen Pro Annual Plan', destination_url='https://example-lumen.com/pricing', commission_type='fixed', commission_value=45, description='B2B SaaS subscription, paid per new annual sign-up.'),
            Offer(advertiser_id=adv3.id, name='Verde Renewal Serum', destination_url='https://example-verde.com/products/renewal-serum', commission_type='percent', commission_value=18, description='Flagship skincare product with high reorder rate.'),
        ])

    db.session.commit()


with app.app_context():
    db.create_all()
    seed_data()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
Done
Good — the correct file is confirmed. But rather than having you paste 600+ lines manually into GitHub's editor (which risks another corruption), let's fix it the clean way directly on PythonAnywhere using the Bash console — one command does the whole job.

Fix it in the PythonAnywhere Bash console
