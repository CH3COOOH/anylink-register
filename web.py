import re
import json
import sqlite3
import time
import os
import sys

import pyotp
from websocket_server import WebsocketServer

class Util:
	def chech_msg(text):
		if len(text) > 64:
			return -1
		try:
			getInfo = eval(text)
		except:
			return -1
		if type(getInfo) != list:
			return -1
		if len(getInfo) != 4:
			return -1
		return getInfo

	def check_input_info(inputList):
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

class DBOP:
	def __init__(self, db_path, iv_path):
		self.db_path = db_path
		self.iv_path = iv_path
		self.ivs = self.load_iv()

	def load_iv(self):
		with open(self.iv_path, 'r') as o:
			self.ivs = json.load(o)['iv']
		return 0

	def update_iv(self):
		with open(self.iv_path, 'w') as o:
			json.dump({'iv': self.ivs}, o)
		return 0

	def use_iv(self, iv):
		if iv in self.ivs:
			del self.ivs[self.ivs.index(iv)]
			self.update_iv()
			return 0
		else:
			return -1

	def update_db(self, username, passwd, email):
		otpSecret = pyotp.random_base32()
		con = sqlite3.connect(self.db_path)
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

class Srv:
	def __init__(self, host, port, db_path, iv_path):
		self.host = host
		self.port = port
		self.ut = Util()
		self.db = DBOP(db_path, iv_path)

	def msgReceived(self, client, server, msg):
		getInfo = self.ut.chech_msg(msg)
		if getInfo == -1:
			return -1
		if self.ut.check_input_info(getInfo) == -1:
			return -1
		user, passwd, email, iv = getInfo
		if self.db.use_iv(iv) == -1:
			return -1
		server.send_message(client, self.db.update_db(username, passwd, email))
		return 0

	def start(self):
		server = WebsocketServer(port=self.port, host=self.host)
		server.set_fn_message_received(self.msgReceived)
		server.run_forever()

if __name__ == '__main__':
	with open(sys.argv[1], 'r') as o:
		conf = json.load(o)
	s = Srv(conf['srv_host'], conf['srv_port'], conf['db_path'], conf['iv_path'])
	s.start()
