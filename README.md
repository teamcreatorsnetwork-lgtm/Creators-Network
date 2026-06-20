{% extends "base.html" %}
{% block title %}Simulate a conversion — Pathway{% endblock %}
{% block body %}
<div class="auth-shell">
  <div class="auth-card" style="max-width: 460px;">
    <div class="brand"><span class="mark"></span>Pathway</div>
    <h1>Simulate a conversion</h1>
    <p class="auth-sub">This page stands in for a merchant's checkout confirmation, which would normally notify Pathway automatically when an order completes.</p>

    <div class="demo-banner">
      <strong>Demo tool.</strong> In production, this step is a server-to-server postback from the advertiser's checkout — not a page a visitor fills in.
    </div>

    {% if link %}
    <p style="font-size: 13.5px; color: var(--muted); margin-bottom: 18px;">
      Tracking code <strong class="mono">{{ link.code }}</strong> → <strong>{{ link.offer.name }}</strong><br>
      Commission: {{ link.offer.commission_label() }}
    </p>
    <form method="POST">
      <input type="hidden" name="code" value="{{ link.code }}">
      <div class="field">
        <label for="order_value">Order value (USD)</label>
        <input type="number" step="0.01" min="0" id="order_value" name="order_value" placeholder="120.00" required>
      </div>
      <button type="submit" class="btn btn-clay btn-block">Record conversion</button>
    </form>
    {% else %}
    <div class="empty-state" style="padding: 20px 0;">
      <p>No tracking code found in this session.<br>Click an affiliate's tracking link first (e.g. <code>/go/&lt;code&gt;</code>), then return here.</p>
    </div>
    <form method="GET" style="display:flex; gap:10px;">
      <input type="text" name="code" placeholder="Or paste a tracking code" style="flex:1; padding:11px 13px; border:1px solid var(--rule); border-radius:3px;">
      <button type="submit" class="btn btn-ghost">Load</button>
    </form>
    {% endif %}
  </div>
</div>
{% endblock %}
