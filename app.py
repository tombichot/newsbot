#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
from urllib import request, parse, error
from datetime import datetime, timedelta
import feedparser
import sqlite3
import requests
from difflib import SequenceMatcher
import telegram
from time import mktime
import config

def isThereSimilarTitle(title, rows):

	ratio = 0.0
	for row in rows:
		r = SequenceMatcher(None, title, row[0]).ratio()
		if r > ratio:
			ratio = r

	if ratio < 0.2:
		return False
	
	return True


def telegram_bot_sendtext(source, title, link):

	keyboard = [[telegram.InlineKeyboardButton("👍", callback_data='Good'),telegram.InlineKeyboardButton("👎", callback_data='Bad')]]
	reply_markup = telegram.InlineKeyboardMarkup(keyboard)

	message = "<b>" + source + "</b>\n" + title + "\n\n" + link
	#data = {'chat_id': bot_chatID,'disable_web_page_preview': 1, 'parse_mode': 'html', 'text': message, 'reply_markup': json.dumps(reply_markup.to_dict())}
	data = {'chat_id': config.bot_chatID,'disable_web_page_preview': 1, 'parse_mode': 'html', 'text': message}

	url = 'https://api.telegram.org/bot' + config.bot_token + '/sendMessage'
	
	r = requests.get(url, data = data)
	results = r.json()

	return results

def start:
	
	conn = sqlite3.connect('./NewsBot.db')
	c = conn.cursor()

	c.execute("CREATE TABLE IF NOT EXISTS news (link text primary key, title text, subject VARCHAR(30), date_added datetime);")

	with open('./filters.json') as json_file:
		data = json.load(json_file)

	for typeOfFeed in data:
		subject = typeOfFeed['subject']
		sources = typeOfFeed['sources']
		include = typeOfFeed['include']
		exclude = typeOfFeed['exclude']

		for source in sources:
			news_feed = feedparser.parse(source['rss-link'])
			i = 0
			for entry in news_feed.entries:
				title = entry.title
				link = entry.link
				if hasattr(entry, 'published'):
					#Check the publication date before precess data, avoids old news if the site has few daily publications
					date = datetime.fromtimestamp(mktime(entry.published_parsed))
					limit = datetime.now() - timedelta(hours=2)
					if date < limit:
						continue
				#Check if title contains good terms and not contains wrong terms
				if any(filter in title.lower() for filter in include) == True and any(filter in title.lower() for filter in exclude) == False:
					print(title)
					#Check if the news is already send to user
					c.execute("SELECT * FROM news WHERE link=? AND subject=?;", (link, subject))
					rows = c.fetchall()
					if len(rows) == 0:
						#The news has never been sent
						#Get all news about the subject
						c.execute("SELECT title FROM news WHERE link!=? AND subject=?;", (link, subject))
						rows = c.fetchall()
						if len(rows) != 0:
							#Check if the news is similar to another already sent
							if isThereSimilarTitle(title, rows) == False:
								#Save the news and send it to user with the telegram bot
								c.execute("INSERT INTO news VALUES (?, ?, ?, ?);", (link, title, subject, datetime.now()))
								conn.commit()
								telegram_bot_sendtext(source['name'], title, link)
						else:
							#Save the news and send it to user with the telegram bot
							c.execute("INSERT INTO news VALUES (?, ?, ?, ?);", (link, title, subject, datetime.now()))
							conn.commit()
							telegram_bot_sendtext(source['name'], title, link)

				# Load only last five news from feed			
				i += 1
				if i == 5: 
					break

	#Delete old news (> 24h)	
	date = datetime.now() - timedelta(days=1)
	c.execute("DELETE FROM news WHERE date_added <= date('now', '-1 day');")
	conn.commit()
	conn.close()
