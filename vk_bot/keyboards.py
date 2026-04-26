from vkbottle import Keyboard, KeyboardButtonColor, Text, OpenLink, Callback

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
        kb.add(Callback(button_text, payload={"set_model": mm}))
        kb.row()
    return kb.get_json()

def build_buy_kb(packs):
    kb = Keyboard(inline=True)
    for price, amount in packs.items():
        kb.add(Callback(f"{amount} ⚡ — {price} руб.", payload={"buy": price, "amount": amount}))
        kb.row()
    kb.add(Callback("⬅️ Назад", payload={"action": "reset_gen"}))
    return kb.get_json()

def build_confirm_kb():
    return (
        Keyboard(inline=True)
        .add(Callback("🚀 Сгенерировать", payload={"action": "confirm_gen"}), color=KeyboardButtonColor.POSITIVE)
        .add(Callback("⚙️ Настройки", payload={"action": "settings_menu"}))
        .row()
        .add(Callback("❌ Отмена", payload={"action": "edit_gen"}), color=KeyboardButtonColor.NEGATIVE)
        .get_json()
    )

def build_settings_kb(current_settings):
    kb = Keyboard(inline=True)
    
    # Aspect Ratios
    ratios = ["1:1", "16:9", "9:16", "3:4", "4:3"]
    cur_ratio = current_settings.get("aspect_ratio", "1:1")
    
    for i, r in enumerate(ratios):
        prefix = "🔘 " if r == cur_ratio else ""
        kb.add(Callback(f"{prefix}{r}", payload={"set_setting": "aspect_ratio", "value": r}))
        if (i + 1) % 3 == 0: kb.row()
    
    kb.row()
    # Formats
    cur_fmt = current_settings.get("output_format", "png")
    for i, fmt in enumerate(["png", "jpg"]):
        prefix = "🔘 " if fmt == cur_fmt else ""
        kb.add(Callback(f"{prefix}{fmt.upper()}", payload={"set_setting": "output_format", "value": fmt}))

    kb.row()
    kb.add(Callback("✅ Готово", payload={"action": "confirm_settings"}), color=KeyboardButtonColor.PRIMARY)
    
    return kb.get_json()

def build_after_gen_kb():
    return (
        Keyboard(inline=True)
        .add(Callback("🔄 Повторить", payload={"action": "repeat_gen"}), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Callback("🗑 Начать заново", payload={"action": "reset_gen"}), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )

def build_pay_link_kb(url):
    return (
        Keyboard(inline=True)
        .add(OpenLink(label="💳 Оплатить", link=url))
        .get_json()
    )
