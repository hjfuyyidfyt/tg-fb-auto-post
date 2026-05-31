path = '/opt/everithing_manager/app/app/keyboards/section_actions.py'
content = open(path).read()

# Check current version
if 'fbpromo:startchat' in content:
    print("Already patched with startchat button")
else:
    old = """    rows = [
        [InlineKeyboardButton(text=\"🚀 New Promo Task\", callback_data=\"fbpromo:newtask\")],
        ["""
    new = """    rows = [
        [InlineKeyboardButton(text=\"💬 Start Promo Chat (Auto)\", callback_data=\"fbpromo:startchat\")],
        [InlineKeyboardButton(text=\"🚀 New Promo Task (Manual)\", callback_data=\"fbpromo:newtask\")],
        ["""
    
    # Find this in the v3 keyboard function
    idx = content.find('def build_facebook_promo_ai_hub_v3_keyboard')
    if idx == -1:
        print("Could not find v3 keyboard function")
    else:
        # Find the pattern after the function definition
        sub = content[idx:]
        pos = sub.find(old)
        if pos == -1:
            print("Could not find rows pattern in v3 function")
            print(repr(sub[:500]))
        else:
            abs_pos = idx + pos
            content = content[:abs_pos] + new + content[abs_pos + len(old):]
            open(path, 'w').write(content)
            print("section_actions.py PATCHED OK")
