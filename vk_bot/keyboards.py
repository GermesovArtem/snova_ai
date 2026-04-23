from vkbottle import Keyboard, KeyboardButtonColor, Text, OpenLink

def build_reply_kb():
    return (
        Keyboard(one_time=False)
        .add(Text("✨ Создать", payload={"cmd": "create"}), color=KeyboardButtonColor.PRIMARY)
        .add(Text("🤖 Модель", payload={"cmd": "model"}), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Text("💳 Баланс", payload={"cmd": "balance"}), color=KeyboardButtonColor.POSITIVE)
        .add(Text("📬 Контакты", payload={"cmd": "contacts"}), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )

def build_model_menu_kb(models, current_model, costs):
    kb = Keyboard(inline=True)
    items = list(models.items())
    for i, (name, mm) in enumerate(items):
        cost = int(costs.get(mm, 1))
        prefix = "✅ " if mm == current_model else ""
        button_text = f"{prefix}{name} ({cost} ⚡)"
        kb.add(Text(button_text, payload={"set_model": mm}))
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

def build_pay_link_kb(url):
    return (
        Keyboard(inline=True)
        .add(OpenLink(label="💳 Оплатить", link=url))
        .get_json()
    )
