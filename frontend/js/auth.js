/* 可选本地演示会话：角色校验在服务端完成，前端只展示当前身份。 */
(function () {
    const state = { enabled: false, user: null, ready: false, pendingLogin: null };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const target = byId("demoLoginStatus");
        target.textContent = message;
        target.className = `dataset-preview ${tone}`.trim();
    }

    function showLogin(show) {
        byId("demoLogin").classList.toggle("hidden", !show);
        document.querySelector(".dashboard").classList.toggle("auth-locked", show);
        if (show) byId("loading").classList.add("hidden");
    }

    function renderUser() {
        const label = byId("demoIdentity");
        const logout = byId("demoLogout");
        if (!state.user) {
            label.classList.add("hidden");
            logout.classList.add("hidden");
            return;
        }
        label.textContent = `${state.user.display_name} · ${state.user.role_label}`;
        label.classList.remove("hidden");
        logout.classList.toggle("hidden", !state.enabled);
    }

    async function login(event) {
        event.preventDefault();
        const button = event.target.querySelector("button[type=submit]");
        button.disabled = true;
        setStatus("登录中");
        try {
            const result = await api.login(byId("demoUsername").value, byId("demoPassword").value);
            state.user = result.user;
            state.ready = true;
            renderUser();
            showLogin(false);
            setStatus("");
            state.pendingLogin?.resolve();
        } catch (error) {
            setStatus(error.message, "error");
        } finally {
            button.disabled = false;
        }
    }

    async function init() {
        const config = await api.getAuthConfig();
        state.enabled = Boolean(config.enabled);
        if (!state.enabled) {
            state.user = { display_name: "本地演示", role_label: "管理员" };
            state.ready = true;
            renderUser();
            return;
        }
        try {
            state.user = (await api.getCurrentUser()).user;
            state.ready = true;
            renderUser();
            showLogin(false);
        } catch (_) {
            showLogin(true);
            await new Promise((resolve, reject) => { state.pendingLogin = { resolve, reject }; });
        }
    }

    async function logout() {
        await api.logout();
        state.user = null;
        renderUser();
        showLogin(true);
        byId("demoPassword").value = "";
    }

    function bind() {
        byId("demoLoginForm").addEventListener("submit", login);
        byId("demoLogout").addEventListener("click", logout);
    }

    window.DemoAuth = { init, bind, getUser: () => state.user };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind, { once: true });
    else bind();
})();
