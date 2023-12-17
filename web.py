import re
import json
import sqlite3
import time
import os

from gevent import monkey
from bottle import request, Bottle, run
import pyotp

## ----------------- Static
PATH = 'sm-reg'
PATH_POST = 'sm-reg'
IVPATH = ''
DBPATH = ''
HOST = '127.0.0.1'
PORT = 8889
CMD_RESTART = 'killall -9 anylink && anylink -c server.toml &'

## ----------------- Public var
app = Bottle()

def check_input(inputList):
	## [user, passwd, email]
	isRight = True
	if len(inputList[0]) < 5:
		print('Wrong username.')
		isRight = False
	if len(inputList[1]) < 8:
		print('Wrong password.')
		isRight = False
	if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", inputList[2]) == None:
		print('Wrong mail.')
		isRight = False
	return isRight

def updateDB(dbname, username, passwd, email):
	otpSecret = pyotp.random_base32()
	con = sqlite3.connect(dbname)
	cur = con.cursor()
	## Is username used
	if len(list(cur.execute('SELECT * FROM User WHERE Username=\'%s\'' % username))) > 0:
		return -1
	lastline = list(cur.execute('SELECT * FROM User ORDER BY Id DESC LIMIT 1'))
	if len(lastline) == 0:
		newid = 0
	else:
		newid = lastline[-1][0] + 1
	sTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
	sql = 'INSERT INTO User VALUES (%d, \'%s\', \'%s\', \'%s\', \'%s\', \'%s\', 1, \'[\"ops\"]\', 1, 0, \'%s\', \'%s\')'\
		% (newid, username, username, email, passwd, pyotp.random_base32(), sTime, sTime)
	cur.execute(sql)
	print(sql)
	con.commit()
	con.close()
	return 0

## ----------------- Web
@app.get('/' + PATH)
def register():
	return '''
	<form action="/%s" method="post">
		Username: <input name="username" type="text" /> 5+ characters <br>
		Password: <input name="password" type="password" /> 8+ characters<br>
		E-mail: <input name="email" type="text" /><br>
		IV. code: <input name="ivcode" type="text" /><br>
	<input type="submit" value="OK">
	</form>
	''' % PATH_POST

@app.post('/' + PATH_POST)
def do_register():
	username = request.forms.get('username')
	password = request.forms.get('password')
	email = request.forms.get('email')
	ivcode = request.forms.get('ivcode')
	# print(username)
	# print(password)
	# print(email)
	# print(ivcode)
	if check_input([username, password, email]) == False:
		return 'Error input detected.'
	with open(IVPATH, 'r') as o:
		ivcode_list = json.load(o)
	if ivcode in ivcode_list.keys():
		if ivcode_list[ivcode] == False:
			return 'IVCode has been used.'
	else:
		return 'Illegal IVCode.'

	if updateDB(DBPATH, username, password, email) < 0:
		return 'Username exist.'
	else:
		# os.system(CMD_RESTART)
		ivcode_list[ivcode] = False
		with open(IVPATH, 'w') as o:
			json.dump(ivcode_list, o)

	return '''
Well done.<br><br>

Server: <br>
Username: %s<br>
Password: ***<br>
Group: opt<br><br>

''' % username


if __name__ == '__main__':
	monkey.patch_all()
	run(app, host=HOST, port=PORT, server='gevent', debug=True, reloader=True)
