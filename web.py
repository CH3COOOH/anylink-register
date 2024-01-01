import re
import json
import sqlite3
import time
import os
import sys
import random
import string

import pyotp
from websocket_server import WebsocketServer

LEN_IV = 16

class Util:
	def check_msg(self, text):
		if len(text) > 128:
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

	def check_input_info(self, inputList):
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
	def __init__(self, isDemo, iv_path, db_path=None):
		self.iv_path = iv_path
		self.ivs = self.load_iv()
		self.db_path = None
		if isDemo == False:
			self.db_path = db_path
		self.demo_mode = 	isDemo

	def load_iv(self):
		with open(self.iv_path, 'r') as o:
			return json.load(o)['iv']
	
	def add_iv(self, iv_new):
		self.ivs.append(iv_new)
		return 0

	def update_iv(self):
		with open(self.iv_path, 'w') as o:
			json.dump({'iv': self.ivs}, o)
		return 0
	
	def get_ivs(self):
		return self.ivs

	def use_iv(self, iv):
		print(iv)
		print(self.ivs)
		if iv in self.ivs:
			del self.ivs[self.ivs.index(iv)]
			self.update_iv()
			return 0
		else:
			return -1

	def update_db(self, username, passwd, email):
		sTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
		if self.demo_mode == False:
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
			sql = 'INSERT INTO User VALUES (%d, \'%s\', \'%s\', \'%s\', \'%s\', \'%s\', 1, \'[\"ops\"]\', 1, 0, \'%s\', \'%s\', )'\
				% (newid, username, username, email, passwd, pyotp.random_base32(), sTime, sTime)
			cur.execute(sql)
			con.commit()
			con.close()
		else:
			sql = 'INSERT INTO User VALUES (%d, \'%s\', \'%s\', \'%s\', \'%s\', \'%s\', 1, \'[\"ops\"]\', 1, 0, \'%s\', \'%s\', )'\
				% (0, username, username, email, passwd, pyotp.random_base32(), sTime, sTime)
		print(sql)
		return 0

class Srv:
	def __init__(self, host, port, isDemo, iv_path, superuser, db_path=None):
		self.host = host
		self.port = port
		self.admin = superuser
		self.ut = Util()
		self.db = DBOP(isDemo, iv_path, db_path)

	def msgReceived(self, client, server, msg):
		print(msg)
		getInfo = self.ut.check_msg(msg)
		if getInfo == -1:
			client["handler"].send_close(1000, b'')
			return -1
		username, passwd, email, iv = getInfo
		## Superuser Mode
		## -----------------
		if username == self.admin[0] and passwd == self.admin[1]:
			print("Superuser login.")
			if iv == '0':
				server.send_message(client, '\n'.join(self.db.get_ivs()))
				return 0
			if iv == '1':
				iv_gen = ''.join(random.sample(string.ascii_letters + string.digits, LEN_IV))
				self.db.add_iv(iv_gen)
				self.db.update_iv()
				server.send_message(client, iv_gen)
				return 0
			if len(iv) != LEN_IV:
				server.send_message(client, "Invalid IV!")
				return -1
			if iv in self.db.get_ivs():
				server.send_message(client, "Same IV exist.")
				return -1
			self.db.add_iv(iv)
			self.db.update_iv()
			server.send_message(client, "OK")
			print(f"New IV added: {iv}")
			return 1
		## -----------------
		if self.ut.check_input_info(getInfo) == -1:
			client["handler"].send_close(1000, b'')
			return -1
		if self.db.use_iv(iv) == -1:
			client["handler"].send_close(1000, b'')
			return -1
		server.send_message(client, str(self.db.update_db(username, passwd, email)))
		client["handler"].send_close(1000, b'')
		return 0

	def start(self):
		server = WebsocketServer(port=self.port, host=self.host)
		server.set_fn_message_received(self.msgReceived)
		print(f"Listening on {self.host}:{self.port}...")
		server.run_forever()

if __name__ == '__main__':
	with open(sys.argv[1], 'r') as o:
		conf = json.load(o)
	if conf['db_path'] == None:
		print('*** RUNNING IN DEMO MODE ***')
		s = Srv(conf['srv_host'], conf['srv_port'], True, conf['iv_path'], conf['admin'])
	else:
		s = Srv(conf['srv_host'], conf['srv_port'], False, conf['iv_path'], conf['admin'], db_path=conf['db_path'])
	s.start()
