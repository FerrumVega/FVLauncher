export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);
        if (url.pathname === "/code") {
            const code = url.searchParams.get("code");

            if (!code) return new Response("code not found", { status: 400 });

            const body = new URLSearchParams({
                client_id: "fvlauncherapp",
                client_secret: env.ELY_CLIENT_SECRET,
                redirect_uri: "http://localhost:3000",
                grant_type: "authorization_code",
                code: code
            });

            const apiResponse = await fetch("https://account.ely.by/api/oauth2/v1/token", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body: body.toString()
            });

            const text = await apiResponse.text();
            return new Response(text, { status: apiResponse.status, headers: { "Content-Type": "application/json" } });
        }
        else if (url.pathname === "/refresh") {
            const token = url.searchParams.get("token");

            if (!token) return new Response("token not found", { status: 400 });

            const body = new URLSearchParams({
                client_id: "fvlauncherapp",
                client_secret: env.ELY_CLIENT_SECRET,
                scope: "account_info offline_access minecraft_server_session",
                grant_type: "refresh_token",
                refresh_token: token
            });

            const apiResponse = await fetch("https://account.ely.by/api/oauth2/v1/token", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body: body.toString()
            });

            const text = await apiResponse.text();
            return new Response(text, { status: apiResponse.status, headers: { "Content-Type": "application/json" } });
        }
    }
};
