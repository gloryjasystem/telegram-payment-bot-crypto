"""
FSM (Finite State Machine) состояния для админ операций
"""
from aiogram.fsm.state import State, StatesGroup


class InvoiceCreationStates(StatesGroup):
    """
    Состояния для пошагового создания инвойса администратором
    
    Процесс создания:
    1. WaitingForUserId - Админ вводит User ID или @username клиента
    2. WaitingForAmount - Админ вводит сумму платежа
    3. WaitingForDescription - Админ вводит описание услуги
    4. PreviewInvoice - Админ видит предпросмотр и подтверждает/отменяет
    
    После подтверждения:
    - Создается инвойс в БД
    - Создается платежная ссылка через Cryptomus
    - Инвойс отправляется клиенту
    - Админ получает подтверждение
    """
    
    # Ожидание User ID клиента
    WaitingForUserId = State()
    
    # Ожидание суммы платежа
    WaitingForAmount = State()
    
    # Ожидание описания услуги
    WaitingForDescription = State()
    
    # Предпросмотр инвойса перед отправкой
    PreviewInvoice = State()


class InvoiceManagementStates(StatesGroup):
    """
    Состояния для управления существующими инвойсами
    
    Используется для:
    - Просмотра деталей инвойса
    - Отмены инвойса
    - Повторной отправки инвойса
    """
    
    # Ожидание Invoice ID для просмотра/управления
    WaitingForInvoiceId = State()
    
    # Подтверждение действия над инвойсом
    ConfirmingAction = State()


# Пример использования в коде:
"""
from aiogram.fsm.context import FSMContext
from states.admin_states import InvoiceCreationStates

# Начало процесса создания инвойса
@router.message(Command("invoice"))
async def start_invoice_creation(message: Message, state: FSMContext):
    await state.set_state(InvoiceCreationStates.WaitingForUserId)
    await message.answer(
        "📝 Создание инвойса\\n\\n"
        "Шаг 1/3: Введите User ID или @username клиента:",
        reply_markup=get_fsm_cancel_keyboard()
    )

# Обработка User ID
@router.message(InvoiceCreationStates.WaitingForUserId)
async def process_user_id(message: Message, state: FSMContext):
    user_id = message.text
    
    # Валидация и сохранение в FSM data
    await state.update_data(user_id=user_id)
    await state.set_state(InvoiceCreationStates.WaitingForAmount)
    
    await message.answer(
        "Шаг 2/3: Введите сумму платежа (например: 150 или 150.50):"
    )

# Обработка суммы
@router.message(InvoiceCreationStates.WaitingForAmount)
async def process_amount(message: Message, state: FSMContext):
    amount = message.text
    
    # Валидация и сохранение
    await state.update_data(amount=amount)
    await state.set_state(InvoiceCreationStates.WaitingForDescription)
    
    await message.answer(
        "Шаг 3/3: Введите описание услуги:"
    )

# Обработка описания
@router.message(InvoiceCreationStates.WaitingForDescription)
async def process_description(message: Message, state: FSMContext):
    description = message.text
    
    # Сохранение и переход к предпросмотру
    await state.update_data(description=description)
    await state.set_state(InvoiceCreationStates.PreviewInvoice)
    
    # Получение всех данных
    data = await state.get_data()
    
    # Показ предпросмотра
    preview_text = f'''
📋 Предпросмотр инвойса

👤 Клиент: {data['user_id']}
💰 Сумма: ${data['amount']}
📝 Описание: {data['description']}

Подтвердить создание инвойса?
'''
    
    await message.answer(
        preview_text,
        reply_markup=get_invoice_preview_keyboard("temp")
    )

# Отмена процесса
@router.callback_query(F.data == "cancel_fsm")
async def cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Создание инвойса отменено")
    await callback.answer()
"""
