import os
import pandas as pd
from datetime import date
from io import BytesIO
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.future import select

from bot.database.base import AsyncSessionLocal
from bot.database.models import Transaction, FinanceCategory, TransactionType, Account

router = Router()

async def _safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "excel:export")
async def cb_export_excel(callback: CallbackQuery):
    await callback.message.edit_text("⏳ Формирую Excel файл с твоей статистикой...")
    
    async with AsyncSessionLocal() as session:
        # Fetch transactions
        stmt = select(Transaction).where(Transaction.user_id == callback.from_user.id)
        txs = (await session.execute(stmt)).scalars().all()
        
        if not txs:
            await callback.message.edit_text("🤷 У тебя пока нет операций для выгрузки.")
            return
            
        # Create DataFrame
        data = []
        for tx in txs:
            data.append({
                "Дата": tx.date.strftime("%d.%m.%Y"),
                "Тип": "Доход" if tx.type == TransactionType.income else "Расход",
                "Сумма": float(tx.amount),
                "Примечание": tx.note or ""
            })
            
        df = pd.DataFrame(data)
        
        # Save to BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Транзакции', index=False)
            
        output.seek(0)
        file = BufferedInputFile(output.read(), filename=f"finance_{date.today().strftime('%Y%m%d')}.xlsx")
        
    await callback.message.answer_document(document=file, caption="Вот твоя история операций в Excel! 📊")
    await callback.message.delete()


@router.message(F.document)
async def process_excel_import(message: Message, state: FSMContext, clear_user_message: callable):
    document = message.document
    if not document.file_name.endswith(('.xls', '.xlsx')):
        return # Игнорируем не-Excel файлы
        
    await _safe_delete(message)
    msg = await message.answer("⏳ Анализирую загруженный Excel файл...")
    
    try:
        # Скачиваем файл
        file_info = await message.bot.get_file(document.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
        
        df = pd.read_excel(downloaded_file)
        
        # Fuzzy поиск колонок
        cols = [c.lower() for c in df.columns]
        
        # Ищем колонку с суммой
        amount_col = None
        for c in ['сумма', 'amount', 'цена', 'расход', 'доход']:
            matches = [col for col in df.columns if c in col.lower()]
            if matches:
                amount_col = matches[0]
                break
                
        # Ищем колонку с датой
        date_col = None
        for c in ['дата', 'date', 'время', 'день']:
            matches = [col for col in df.columns if c in col.lower()]
            if matches:
                date_col = matches[0]
                break
                
        if not amount_col:
            await msg.edit_text("❌ Не удалось найти колонку с суммой (искал: 'сумма', 'amount', 'цена').")
            return
            
        async with AsyncSessionLocal() as session:
            # Получаем основной счет
            from bot.database.models import User
            user = await session.get(User, message.from_user.id)
            if not user.main_account_id:
                await msg.edit_text("❌ Сначала создай хотя бы один счёт в разделе Финансы.")
                return
                
            imported_count = 0
            for index, row in df.iterrows():
                try:
                    amt = float(row[amount_col])
                    if pd.isna(amt): continue
                    
                    tx_date = date.today()
                    if date_col and not pd.isna(row[date_col]):
                        try:
                            # Пытаемся распарсить дату pandas
                            dt = pd.to_datetime(row[date_col])
                            tx_date = dt.date()
                        except:
                            pass
                            
                    tx_type = TransactionType.expense if amt < 0 else TransactionType.income
                    amt = abs(amt)
                    
                    tx = Transaction(
                        user_id=message.from_user.id,
                        account_id=user.main_account_id,
                        amount=amt,
                        type=tx_type,
                        date=tx_date,
                        note="Импорт из Excel"
                    )
                    session.add(tx)
                    
                    # Обновляем баланс
                    acc = await session.get(Account, user.main_account_id)
                    if tx_type == TransactionType.income:
                        acc.balance += amt
                    else:
                        acc.balance -= amt
                        
                    imported_count += 1
                except Exception as e:
                    continue # Пропускаем битые строки
                    
            if imported_count > 0:
                await session.commit()
                await msg.edit_text(f"✅ Успешно импортировано {imported_count} операций!")
            else:
                await msg.edit_text("🤷 В файле не найдено корректных данных для импорта.")
                
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка при чтении файла: {e}")


@router.callback_query(F.data == 'excel:import')
async def cb_import_excel(callback: CallbackQuery):
    await callback.message.edit_text('📥 <b>Импорт из Excel</b>\n\nПросто отправь мне файл .xls или .xlsx со своими транзакциями. Я попытаюсь найти в нем колонки <b>Сумма</b> и <b>Дата</b> и импортировать их в твой основной счет.\n\n<i>Все нераспознанные строки будут пропущены.</i>', parse_mode='HTML')
    await callback.answer()
