from vkbottle import Keyboard, KeyboardButtonColor, Text

def build_reply_kb():
    return (
        Keyboard(one_time=False, resize_keyboard=True)
        .add(Text("✨ Создать"), color=KeyboardButtonColor.PRIMARY)
        .add(Text("🤖 Модель"), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Text("💳 Баланс"), color=KeyboardButtonColor.POSITIVE)
        .add(Text("📬 Контакты"), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )

def build_model_menu_kb(models, current_model, costs):
    kb = Keyboard(inline=True)
    # Using a list to ensure order and avoid dictionary key issues
    items = list(models.items())
    for i, (name, mm) in enumerate(items):
        cost = int(costs.get(mm, 1))
        prefix = "✅ " if mm == current_model else ""
        button_text = f"{prefix}{name} ({cost} ⚡)"
        kb.add(Text(button_text, payload={"set_model": mm}))
        if (i + 1) % 1 == 0: # One per row for clarity
             kb.row()
    return kb.get_json()

def build_buy_kb(packs):
    kb = Keyboard(inline=True)
    for price, amount in packs.items():
        kb.add(Text(f"{amount} ⚡ — {price} руб.", payload={"buy": price, "amount": amount}))
        kb.row()
    kb.add(Text("⬅️ Назад", payload={"menu": "main"}))
    return kb.get_json()

def build_confirm_kb():
    return (
        Keyboard(inline=True)
        .add(Text("✅ Сгенерировать", payload={"action": "confirm_gen"}), color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Text("❌ Отмена", payload={"action": "edit_gen"}), color=KeyboardButtonColor.NEGATIVE)
        .get_json()
    )

def build_after_gen_kb():
    return (
        Keyboard(inline=True)
        .add(Text("🔄 Повторить", payload={"action": "repeat_gen"}), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Text("🖼 Начать заново", payload={"menu": "main"}), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )
