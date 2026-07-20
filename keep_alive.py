import os
from aiohttp import web

async def handle(request):
    return web.Response(text="Bot is alive!")

def run_keep_alive():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, port=port)

if __name__ == "__main__":
    run_keep_alive()
