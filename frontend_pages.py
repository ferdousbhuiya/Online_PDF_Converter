from flask import render_template


def build_categories(tools):
    categories = {
        'organize': {'name': 'Organize PDF', 'tools': []},
        'convert': {'name': 'Convert PDF', 'tools': []},
        'edit': {'name': 'Edit PDF', 'tools': []},
        'optimize': {'name': 'Optimize PDF', 'tools': []},
        'security': {'name': 'PDF Security', 'tools': []},
    }
    for tool in tools:
        category = tool.get('category')
        if category in categories:
            categories[category]['tools'].append(tool)
    return categories


def make_home_view(original_app):
    def home():
        return render_template('index.html', tools=original_app.TOOLS)
    home.__name__ = 'index'
    return home


def make_tools_view(original_app):
    def tools_page():
        categories = build_categories(original_app.TOOLS)
        return render_template('tools.html', categories=categories, tools=original_app.TOOLS)
    return tools_page


def about_page():
    return render_template('about.html')


def contact_page():
    return render_template('contact.html')
