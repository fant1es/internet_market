import asyncio
from app.services.email_service import send_email

async def main():
    ok = await send_email(
        to="your_email@gmail.com",
        subject="Тест SMTP",
        text="SMTP работает",
        html="<b>SMTP работает</b>",
    )
    print("OK" if ok else "FAIL, смотри лог")

asyncio.run(main())