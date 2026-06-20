{% extends "base.html" %}
{% block title %}Sign up — Pathway{% endblock %}
{% block body %}
<div class="auth-shell">
  <div class="auth-card">
    <div class="brand"><span class="mark"></span>Pathway</div>
    <h1>Create your account</h1>
    <p class="auth-sub">Start generating tracking links in under a minute.</p>

    <form method="POST">
      <div class="field">
        <label for="name">Full name</label>
        <input type="text" id="name" name="name" placeholder="Jordan Lee" required>
      </div>
      <div class="field">
        <label for="email">Email</label>
        <input type="email" id="email" name="email" placeholder="you@example.com" required>
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" placeholder="At least 8 characters" required minlength="8">
        <div class="hint">Use 8 or more characters.</div>
      </div>
      <button type="submit" class="btn btn-primary btn-block">Create account</button>
    </form>

    <div class="auth-switch">Already have an account? <a href="/login">Log in</a></div>
  </div>
</div>
{% endblock %}
