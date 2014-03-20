import random
from flask import Flask, render_template, request

##
## Our WSGI application .. in this case Flask based
##
app = Flask(__name__)


@app.route('/')
def page_home():
   return render_template('index.html', message = "Hello from Crossbar.io")


@app.route('/call')
def page_call():
   return render_template('call.html')


@app.route('/square', methods = ['POST', 'GET'])
def page_square():
   if request.method == 'POST':
      value = int(request.form['value'])
   else:
      value = random.randint(0, 100)
   return render_template('square.html', value = value)



if __name__ == "__main__":
   app.run (port = 8090, debug = True)
