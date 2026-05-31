import sys
path = '/opt/everithing_manager/app/app/main.py'
content = open(path).read()
old_line = '    dispatcher.include_router(register_navigation_handlers(dependencies["context"]))\n    schedule_runner'
new_line = '    dispatcher.include_router(register_navigation_handlers(dependencies["context"]))\n    dispatcher.include_router(register_facebook_promo_chat(dependencies["context"]))\n    schedule_runner'
if old_line in content:
    content = content.replace(old_line, new_line)
    open(path, 'w').write(content)
    print("main.py PATCHED OK")
else:
    print("Already patched or pattern not found")
    print(repr(content[700:900]))
