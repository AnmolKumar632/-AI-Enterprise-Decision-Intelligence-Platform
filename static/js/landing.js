/* ==========================================================================
   AEDIP Enterprise Marketing — shared interactions
   ========================================================================== */

(function () {
    'use strict';

    /* ---------- Navigation active state ---------- */
    function initNav() {
        var links = document.querySelectorAll('.nav-link-custom[data-nav]');
        if (!links.length) return;
        var current = window.location.pathname;
        var hash = window.location.hash;
        links.forEach(function (link) {
            var target = link.getAttribute('data-nav');
            var isActive = false;
            if (target === current) {
                isActive = true;
            } else if (target.indexOf('#') === 0 && hash === target && current.indexOf('/auth/') !== -1) {
                isActive = true;
            }
            if (isActive) {
                link.classList.add('active');
            }
        });
    }

    /* ---------- Scroll reveal ---------- */
    function initReveal() {
        var els = document.querySelectorAll('.reveal');
        if (!els.length) return;
        if (!('IntersectionObserver' in window)) {
            els.forEach(function (el) { el.classList.add('visible'); });
            return;
        }
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });
        els.forEach(function (el) { observer.observe(el); });
    }

    /* ---------- Auth modal helpers ---------- */
    function showAlert(el, msg) {
        if (!el) return;
        el.innerText = msg;
        el.style.display = "block";
    }

    function hideAlerts() {
        var alertBox = document.getElementById('modalAlert');
        var successBox = document.getElementById('modalSuccess');
        if (alertBox) alertBox.style.display = "none";
        if (successBox) successBox.style.display = "none";
    }

    function switchAuthTab(mode) {
        hideAlerts();
        var loginPanel = document.getElementById('authPanelLogin');
        var registerPanel = document.getElementById('authPanelRegister');
        var loginBtn = document.getElementById('authTabLoginBtn');
        var regBtn = document.getElementById('authTabRegisterBtn');
        if (!loginPanel || !registerPanel || !loginBtn || !regBtn) return;
        var isLogin = mode === 'login';
        loginPanel.style.display = isLogin ? "block" : "none";
        registerPanel.style.display = isLogin ? "none" : "block";
        loginBtn.classList.toggle('btn-glow', isLogin);
        loginBtn.classList.toggle('btn-ghost', !isLogin);
        regBtn.classList.toggle('btn-glow', !isLogin);
        regBtn.classList.toggle('btn-ghost', isLogin);
    }

    function submitModalAuth() {
        var email = document.getElementById('modalEmail');
        var password = document.getElementById('modalPassword');
        var alertBox = document.getElementById('modalAlert');
        var successBox = document.getElementById('modalSuccess');
        if (!email || !password) return;
        hideAlerts();
        if (!email.value.trim() || !password.value) {
            showAlert(alertBox, "Please fill in all fields.");
            return;
        }
        fetch('/auth/api/login/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email.value.trim(), password: password.value })
        })
        .then(function (res) {
            if (!res.ok) {
                return res.json().then(function (err) { throw new Error(err.error || "Login failed"); });
            }
            return res.json();
        })
        .then(function (data) {
            var d = new Date();
            d.setTime(d.getTime() + (24 * 60 * 60 * 1000));
            document.cookie = "access_token=" + data.token + ";expires=" + d.toUTCString() + ";path=/";
            localStorage.setItem('access_token', data.token);
            showAlert(successBox, "Login successful! Redirecting...");
            setTimeout(function () { window.location.href = '/'; }, 800);
        })
        .catch(function (err) {
            showAlert(alertBox, err.message);
        });
    }

    function submitModalRegister() {
        var first_name = document.getElementById('regFirst');
        var last_name = document.getElementById('regLast');
        var email = document.getElementById('regEmail');
        var password = document.getElementById('regPassword');
        var role = document.getElementById('regRole');
        var alertBox = document.getElementById('modalAlert');
        var successBox = document.getElementById('modalSuccess');
        if (!first_name || !last_name || !email || !password || !role) return;
        hideAlerts();
        if (!first_name.value.trim() || !last_name.value.trim() || !email.value.trim() || !password.value) {
            showAlert(alertBox, "Please fill in all fields.");
            return;
        }
        fetch('/auth/api/register/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                first_name: first_name.value.trim(),
                last_name: last_name.value.trim(),
                email: email.value.trim(),
                password: password.value,
                role: role.value
            })
        })
        .then(function (res) {
            if (!res.ok) {
                return res.json().then(function (err) { throw new Error(err.error || "Registration failed"); });
            }
            return res.json();
        })
        .then(function (data) {
            var verifyUrl = '/auth/api/verify/' + data.verification_token + '/';
            successBox.innerHTML = 'Registration successful! <br>' +
                '<a href="' + verifyUrl + '" class="fw-bold text-decoration-underline" style="color: var(--accent-cyan);">Click here to simulate email verification</a><br>' +
                '<span class="small">Then sign in to continue.</span>';
            successBox.style.display = "block";
            first_name.value = '';
            last_name.value = '';
            email.value = '';
            password.value = '';
            setTimeout(function () { switchAuthTab('login'); }, 3000);
        })
        .catch(function (err) {
            showAlert(alertBox, err.message);
        });
    }

    /* ---------- Scenario simulator hint ---------- */
    function initScenario() {
        var cards = document.querySelectorAll('.scenario-card[data-hint]');
        cards.forEach(function (card) {
            card.addEventListener('click', function () {
                var hint = card.getAttribute('data-hint');
                if (!hint) return;
                cards.forEach(function (c) { c.querySelector('.scenario-hint') && (c.querySelector('.scenario-hint').style.display = 'none'); });
                var el = card.querySelector('.scenario-hint');
                if (el) el.style.display = 'block';
                card.classList.add('recommended');
                cards.forEach(function (c) { if (c !== card) c.classList.remove('recommended'); });
            });
        });
    }

    /* ---------- Boot ---------- */
    document.addEventListener('DOMContentLoaded', function () {
        initNav();
        initReveal();
        initScenario();
    });

    /* Expose for inline on* handlers used by templates */
    window.showAlert = showAlert;
    window.hideAlerts = hideAlerts;
    window.switchAuthTab = switchAuthTab;
    window.submitModalAuth = submitModalAuth;
    window.submitModalRegister = submitModalRegister;
})();
