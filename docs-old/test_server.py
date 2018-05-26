# coding=utf8

import uuid

from flask import Flask, render_template

from markdown import DocPages, get_git_latest_commit

# Jinja2 extension for Pygments
import jinja2_highlight

class MyFlask(Flask):
   jinja_options = dict(Flask.jinja_options)
   jinja_options.setdefault('extensions',[]).append('jinja2_highlight.HighlightExtension')

# Flask app object
#
app = MyFlask(__name__, static_folder='static', template_folder='templates')
app.secret_key = str(uuid.uuid4())


@app.route('/')
def page_home():
   return render_template('index.html')


@app.route('/docs/<path:path>/')
def page_docs(path = None):
   if path is None or path.strip() == "":
      title = 'Documentation'
      path = 'Documentation'
   else:
      title = path.replace('-', ' ')

   last_commit = app.latest_doc_commit

   contents = app.pages_docs.render(path)

   if contents:
      return render_template('page.html', contents=contents, title=title, last_commit=last_commit)
   else:
      return "no such page"


if __name__ == "__main__":

   print("Processing Markdown pages from docs/pages ..")
   app.pages_docs = DocPages('./docs/pages')

   app.latest_doc_commit = get_git_latest_commit('./.git')

   app.run(host="0.0.0.0", port=8080, debug=True)
