{% extends "base.html" %}
{% block title %}Payouts — Pathway{% endblock %}
{% block body %}
<div class="app-shell">
  {% include "_affiliate_sidebar.html" with context %}
  {% set active = 'payouts' %}

  <main class="app-main">
    <div class="page-head">
      <div>
        <h1>Payouts</h1>
        <p>Request a payout against your available balance.</p>
      </div>
    </div>

    <div class="stat-cards cols-3">
      <div class="stat-card">
        <div class="sc-label">Available balance</div>
        <div class="sc-val accent mono">${{ '%.2f'|format(affiliate.balance()) }}</div>
      </div>
      <div class="stat-card">
        <div class="sc-label">Total earned</div>
        <div class="sc-val mono">${{ '%.2f'|format(affiliate.total_earned()) }}</div>
      </div>
      <div class="stat-card">
        <div class="sc-label">Pending requests</div>
        <div class="sc-val mono">{{ history|selectattr('status','equalto','pending')|list|length }}</div>
      </div>
    </div>

    <div class="panel">
      <h2>Request a payout</h2>
      <p class="panel-sub">Funds are reviewed by the network before being marked as paid.</p>

      {% if affiliate.balance() > 0 %}
      <form method="POST" style="display:flex; gap:12px; align-items:flex-end; max-width: 420px;">
        <div class="field" style="margin-bottom:0; flex:1;">
          <label for="amount">Amount (USD)</label>
          <input type="number" step="0.01" min="0.01" max="{{ affiliate.balance() }}" name="amount" id="amount" placeholder="0.00" required>
        </div>
        <button type="submit" class="btn btn-primary">Request payout</button>
      </form>
      {% else %}
      <div class="empty-state" style="padding: 24px;">
        <p>No available balance yet. Drive a conversion to start earning.</p>
      </div>
      {% endif %}
    </div>

    <div class="panel" style="margin-bottom:0;">
      <h2>Request history</h2>
      <p class="panel-sub">Status of every payout you've requested.</p>

      {% if history %}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Requested</th>
              <th class="t-right">Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {% for p in history %}
            <tr>
              <td class="mono">{{ p.requested_at.strftime('%b %d, %Y') }}</td>
              <td class="t-right mono">${{ '%.2f'|format(p.amount) }}</td>
              <td>
                {% if p.status == 'paid' %}
                  <span class="badge badge-green">Paid</span>
                {% elif p.status == 'rejected' %}
                  <span class="badge badge-clay">Rejected</span>
                {% else %}
                  <span class="badge badge-muted">Pending</span>
                {% endif %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      {% else %}
      <div class="empty-state">
        <div class="es-icon">—</div>
        <p>No payout requests yet.</p>
      </div>
      {% endif %}
    </div>
  </main>
</div>
{% endblock %}
