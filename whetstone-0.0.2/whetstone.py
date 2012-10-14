#!/usr/bin/env python

# Whetstone
# A tool to help you memorise scripture

#
# Whetstone - Helping you keep your Sword sharp
# Copyright (C) 2009 Ben Thorp ( mrben@jedimoose.org )
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

# v0.0.2
# Still requires Diatheke, but will work with any installed SWORD modules
# Quiz page up and running for multiple choice quizzes
# Various bugfixes in planners - note that planners from v0.0.1 will lose the end date
# Preferences page to choose Translation and Default Planner

# v0.0.1
# Requires Diatheke and the ESV bible module to be installed

import sys, commands, re, datetime, string, ConfigParser, os, random
try:
	import pygtk
	pygtk.require("2.0")
except:
	pass
	
try:
	import gtk
	import gtk.glade
	import gobject
	import pango
except:
	sys.exit(1)

from pysqlite2 import dbapi2 as sqlite
import xdg.BaseDirectory

diatheke_test = commands.getoutput("which diatheke")
if (diatheke_test == ""):
	print "Unable to locate diatheke; you will not be able to pull scripture verses"
else:
	print "Located diatheke at "+diatheke_test


# Load preferences
config_path = xdg.BaseDirectory.save_config_path("whetstone")
config = ConfigParser.RawConfigParser()
global current_translation
global current_planner
current_translation = 'ESV'
current_planner = 'None'
if (os.path.exists(os.path.join(config_path,'.whetstone'))):
	config.read(os.path.join(config_path,'.whetstone'))
	current_translation = config.get("Section1", "translation")
	current_planner = config.get("Section1", "default_planner")
else:
	# Create config file
	config.add_section('Section1')
	config.set('Section1','translation','ESV')
	config.set('Section1','default_planner','None')
	with open(os.path.join(config_path, '.whetstone'), 'wb') as configfile:
		config.write(configfile)

# Static translation to start with; need to add this to the preferences.
#tr = "ESV"

def strip_text(verse):
	''' Takes a text from the Sword project and strips out all the notes '''
	temp = verse.split('\n')[:-1]
	output = ""
	for line in temp:
		if (line!=""):
			output += re.sub('^.*?:.*?: ','',line)
			output += "\n"
	return unicode(output)

def split_verse(verse):
	''' Return a tuple of book, chapter, verse when given a reference '''
	temp1 = verse.split(':')
	# This gives us [book chapter] and [verses]
	if (len(temp1) > 1):
		verses = temp1[1]
	else:
		verses = "ALL"
	temp2 = temp1[0].split(' ')
	chapter = temp2[-1]
	book = " ".join(temp2[:-1])

	return (book, chapter, verse)

def join_verse(verse):
	''' Return a string when given a verse tuple '''
	if (verse[2] == "ALL"):
		return verse[0]+" "+verse[1]
	else:		
		return verse[0]+" "+verse[1]+":"+verse[2]

def ellipsize(text, size=50):
	''' Return a string of size 'size' with ellipses where truncated '''
	if len(text) > size:
		return text[:size-3]+"..."
	else:
		return text

def get_translations_from_sword():
	''' Return a list of translations available from SWORD in the format [name,description] '''

	raw_modules = commands.getoutput('diatheke -b system -k modulelist')
	tr_list = []
	# Need to divide up and only pull the bible translations and not other books and commentaries
	temp = raw_modules.split(":\n")
	for item in temp[1].split('\n')[:-1]:
		temp2 = item.split(' : ')
		tr_list.append(temp2)

	return tr_list

def bylength(word1, word2):
	"""
	# write your own compare function:
	# returns value > 0 of word1 longer then word2
	# returns value = 0 if the same length
	# returns value < 0 of word2 longer than word1
	"""
	return len(word2) - len(word1)

def stars(word):
	''' Return *s for a given word '''
	return "".join(["*" for letter in word])

class MVDB():
	''' This defines the sqlite database '''
	def __init__(self):
		self.con = sqlite.connect('./.pymv_db')
		self.cur = self.con.cursor()

		flag = 0
		# Create the tables if they don't already exist
		try:
			self.cur.execute("CREATE TABLE cats(refno INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, cat VARCHAR)")
			self.cur.execute("CREATE TABLE verses(refno INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, catref INTEGER, book VARCHAR, chapter INTEGER, verse VARCHAR, verseref VARCHAR, versetext VARCHAR)")
			self.cur.execute("CREATE TABLE planner(date DATE, verseref INTEGER, name VARCHAR)")
			self.cur.execute("CREATE TABLE quiz(verseref INTEGER, word VARCHAR, option VARCHAR)")
			self.con.commit()
			flag = 1
		except sqlite.OperationalError:
			print "DB Already Exists"

		if (flag == 1):
			print "Created the DB. Adding categories and verses"
			# Insert the "100 best verses to learn" into the verses table, and all the categories into the category table
			verses = open('verses.csv', 'r').readlines()
			for verseline in verses:
				# Add the category
				data = verseline[:-1].split('\t')
				category = data[0]
				print category
				self.cur.execute("INSERT INTO cats(cat) VALUES(?)", (category,))
				print "Added category "+category
				# Get the reference
				catref = self.cur.lastrowid

				# Add each verse
				for verse in data[1:]:
					versetext = strip_text(commands.getoutput("diatheke -b "+current_translation+" -k "+verse))
					verseref = unicode(verse)
					book, chapter, verse = split_verse(verseref)
					self.cur.execute("INSERT INTO verses(catref, book, chapter, verse, verseref, versetext) VALUES(?, ?, ?, ?, ?, ?)", (catref, book, chapter, verse, verseref, versetext))
					print "\t Added verse "+verse	
				self.con.commit()

	def cat_list(self, refs=True):
		''' Return a list of categories from the database, either in the format {'ref':ref, 'title':title} or a straight list of strings'''
		self.cur.execute("SELECT refno, cat FROM cats ORDER BY cat")
		raw_cat = self.cur.fetchall()
		cat_list = []
		for item in raw_cat:
			if (refs):
				temp = {}
				temp['ref'] = item[0]
				temp['title'] = item[1]
				cat_list.append(temp)
			else:
				cat_list.append(item[1])
		return cat_list

	def verse_list(self, catref=0):
		''' Return a list of verses (reference and id) for a given category (or all if none given) '''
		if (catref != 0):
			self.cur.execute("SELECT verseref, refno FROM verses WHERE catref=?",(catref,))
		else:
			self.cur.execute("SELECT verseref, refno FROM verses")
		raw_verses = self.cur.fetchall()
		verse_list = []
		for item in raw_verses:
			verse_list.append((item[0],item[1]))

		return verse_list

	def get_verse(self, verseid=1):
		''' Return a verse based on the DB ID, in the format [verseref, versetext] '''
		self.cur.execute("SELECT verseref, versetext FROM verses WHERE refno="+str(verseid))
		raw_text = self.cur.fetchall()
		return [raw_text[0][0], raw_text[0][1]]

	def get_random_verses(self, count=1, type="Verse", avoid = 0):
		''' Get 'count' verses, and return as a list, either the text or the ref of the verse, avoiding the reference given '''

		if type == 'Verse':
			field = 'verseref'
		else:
			field = 'versetext'
		verselist = []
		self.cur.execute("SELECT COUNT(verseref) FROM verses")
		max = self.cur.fetchall()[0][0]
		for item in range(count):
			id = random.randint(0, max)
			flag = 0
			while (flag==0):
				try:
					self.cur.execute("SELECT "+field+" FROM verses WHERE refno = "+str(id)) 
					tempid = self.cur.fetchall()[0][0]
					if (tempid != avoid):
						verselist.append(tempid)
						flag = 1
				except:
					id = random.randint(0, max)			
		return verselist

	def delete_verse(self, verseid):
		''' Delete a verse from the database '''
		self.cur.execute("DELETE FROM verses WHERE refno=?", (verseid,))
		# Not sure what to do with empty categories - maybe a tidy up function on exit? 
		self.con.commit()

	def add_category(self, category):
		''' Add a category to the database '''
		self.cur.execute("INSERT INTO cats(cat) VALUES (?)", (category,))
		self.con.commit()

	def get_category_id(self, category):
		''' Given a category title, find the reference '''
		self.cur.execute("SELECT refno FROM cats WHERE cat=?", (category,))
		results = self.cur.fetchall()
		return results[0][0]

	def add_verse(self, verseref, versetext, category):
		''' Add a verse to the database, given the reference, text and category title '''

		book, chapter, verse = split_verse(verseref)
		catid = self.get_category_id(category)
		self.cur.execute("INSERT INTO verses(catref, book, chapter, verse, verseref, versetext) VALUES (?,?,?,?,?,?)", (catid,book,chapter,verse,verseref,versetext))
		self.con.commit()


	def planner_list(self):
		''' Return a list of the planners in the database '''
		self.cur.execute("SELECT DISTINCT name FROM planner")
		raw_results = self.cur.fetchall()
		planners = []
		for item in raw_results:
			planners.append(item[0])
		return planners

	def verse_count(self, cat_list = []):
		''' Count the number of verses in the given categories '''
		if len(cat_list) == 0:
			return 0
		else:
			verses = 0
			sql = "SELECT count(refno) FROM verses WHERE catref IN ("
			for cat in cat_list:
				sql += str(cat)+","
			# remove the trailing slash
			sql = sql[:-1]+")"
			self.cur.execute(sql)
			return self.cur.fetchall()[0][0]			

	def add_verse_to_planner(self, planner, verse, date):
		''' Add a verse into the planner table - all date handling is done in the client '''
		self.cur.execute("INSERT INTO planner(date, verseref, name) VALUES (?,?,?)", (date, verse, planner))
		self.con.commit()

	def todays_verse(self, planner, date='now'):
		''' Return the appropriate verse for today, given a particular planner, in the format [verseref, versetext, date] '''
		self.cur.execute("SELECT a.verseref, a.versetext, b.date FROM verses AS a, planner AS b WHERE a.refno = (SELECT verseref FROM planner WHERE date <= date('"+date+"') AND name='"+planner+"' ORDER BY date DESC LIMIT 1) AND b.date = (SELECT date FROM planner WHERE date <= date('"+date+"') AND name = '"+planner+"' ORDER BY date DESC LIMIT 1)")
		raw_result = self.cur.fetchall()
		if len(raw_result) == 0:
			return -1
		else:
			return [raw_result[0][0], raw_result[0][1], raw_result[0][2]]

	def next_and_last(self, planner, date='now'):
		''' Return the previous and next dates on the given planner, in the format [last,next] '''
		self.cur.execute("SELECT date FROM planner WHERE date <= date('"+date+"') AND name = '"+planner+"' ORDER BY date DESC LIMIT 1")
		raw_text = self.cur.fetchall()
		if len(raw_text) == 0:
			last = -1
		else:
			last = raw_text[0][0]
		self.cur.execute("SELECT date FROM planner WHERE date > date('"+date+"') AND name = '"+planner+"' ORDER BY date ASC LIMIT 1")
		raw_text = self.cur.fetchall()
		if len(raw_text) == 0:
			next = -1
		else:
			next = raw_text[0][0]
		return [last, next]

	def get_planner_dates(self, planner, month, year):
		''' Return a list of all the dates in the planner for a given month '''
		self.cur.execute("SELECT strftime('%d',date) FROM planner WHERE name='"+planner+"' and strftime('%m-%Y', date) = '"+month+"-"+year+"'")
		raw_dates = self.cur.fetchall()
		date_list = []
		for item in raw_dates:
			date_list.append(item[0])
		# Last value in any planner is the dummy end_date, so we ignore in this list
		return date_list[:-1]

	def get_verselist_todate(self, planner, date='now', limit = 0):
		''' Return a list of verse IDs from the planner, up to today '''
		if (limit == 0):
			self.cur.execute("SELECT verseref FROM planner WHERE name = '"+planner+"' AND date <= ('"+date+"') ORDER BY date DESC")
		else:
			self.cur.execute("SELECT verseref FROM planner WHERE name = '"+planner+"' AND date <= ('"+date+"') ORDER BY date DESC LIMIT "+str(limit))
		raw_output = self.cur.fetchall()
		output = []
		for item in raw_output:
			output.append(item[0])
		return output 

	def get_cat_from_verse(self, verse):
		''' Given a verse, get a category that contains that verse '''
		# Note - currently this doesn't work properly with verses that are in multiple categories 

		self.cur.execute("SELECT cat FROM cats WHERE refno IN (SELECT catref FROM verses WHERE verseref = '"+verse+"')")
		return self.cur.fetchall()[0][0]

class guiClient:
	''' This is the main application '''
	def __init__(self):
		# Set the glade file
		self.gladefile = 'whetstone.glade'''
		self.wTree = gtk.glade.XML(self.gladefile)

		# Create our event dictionary and connect it
		dic = {"on_swordbutton_clicked" : self.OnSword,
				"on_mainwindow_destroy" : self.OnQuit,
				"on_addbutton_clicked" : self.OnAdd,
				"on_deletebutton_clicked" : self.OnDelete,
				"on_clearbutton_clicked" : self.OnClear,
				"on_treeview1_row_activated" : self.OnLoadVerse,
				"on_notebook1_switch_page" : self.OnChangePage,
				"on_slider_value_changed" : self.OnSliderChange,
				"on_homebutton_clicked" : self.OnSliderButton,
				"on_lessbutton_clicked" : self.OnSliderButton,
				"on_morebutton_clicked" : self.OnSliderButton,
				"on_endbutton_clicked" : self.OnSliderButton,
				"on_newplannerbutton_clicked" : self.OnPlannerWizard,
				"on_treeview2_row_activated" : self.OnLoadPlanner,
				"on_calendar1_day_selected" : self.OnPlannerDateChange,
				"on_calendar1_month_changed" : self.OnPlannerMonthChange,
				"on_about1_activate" : self.About,
				"on_preferences1_activate" : self.Preferences,
				"on_plannerquiz_clicked" : self.OnQuizLaunch,
				"on_categoryquiz_clicked" : self.OnQuizLaunch,
				"on_quizfirst_clicked" : self.OnQuizButton,
				"on_quizback_clicked" : self.OnQuizButton,
				"on_quiznext_clicked" : self.OnQuizButton,
				"on_quizlast_clicked" : self.OnQuizButton,
				"on_choicea_clicked" : self.OnQuizAnswer,
				"on_choiceb_clicked" : self.OnQuizAnswer,
				"on_choicec_clicked" : self.OnQuizAnswer,
				"on_choiced_clicked" : self.OnQuizAnswer,
				"on_quizfinish_clicked" : self.OnQuizFinish,
				"on_resultsbutton_clicked" : self.OnResultsFinish,
				"on_results_close" : self.OnResultsFinish,
				"on_results_destroy" : self.OnResultsFinish,
				}
		self.wTree.signal_autoconnect(dic)

		# Setup the DB
		self.db = MVDB()

		# *********************************************************************
		#                       Add/Edit Verse Tab
		# *********************************************************************

		# Set up the treeview
		self.catview = self.wTree.get_widget("treeview1")
		self.catview.set_level_indentation(0)
		self.treestore = gtk.TreeStore(str, str, str)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Category", renderer, markup = 0)
		column.set_resizable(True)
		self.catview.append_column(column)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Verse", renderer, markup = 0)
		column.set_visible(False)
		column.set_resizable(True)
		self.catview.append_column(column)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("DB_ID", renderer, markup = 0)
		column.set_visible(False)
		self.catview.append_column(column)

		# The dropdown
		self.cat_dropdown = self.wTree.get_widget("categorydropdown")

		# Store the verse database ID
		self.verseid = 0

		# *********************************************************************
		#                       Learning Tab
		# *********************************************************************

		self.plannerview = self.wTree.get_widget("treeview2")
		self.plannerstore = gtk.TreeStore(str)
		self.learn_text = self.wTree.get_widget("learntext")
		self.learn_ref = self.wTree.get_widget("learnref")
		self.slider = self.wTree.get_widget("slider")

		self.show_verse = self.wTree.get_widget("showverse")
		self.show_cat = self.wTree.get_widget("showcat")
		self.show_text = self.wTree.get_widget("showtext").get_buffer()

		# Make sure the exander is closed
		self.wTree.get_widget("plannerexpander").set_expanded(False)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Title", renderer, markup = 0)
		column.set_resizable(True)
		self.plannerview.append_column(column)

		self.default_planner = "Test Weekly"
		self.planner_date = "now"

		# *********************************************************************
		#                       Quiz Tab
		# *********************************************************************

		# Setup the planner dropdown
		self.quizplannerdropdown = self.wTree.get_widget("quizplannerdropdown")

		# Setup the quiz category box
		self.quizview = self.wTree.get_widget("quizcatview")
		self.quizstore = gtk.TreeStore(str)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Title", renderer, markup = 0)
		column.set_resizable(True)
		self.quizview.append_column(column)

		# *********************************************************************
		#                       Quiz Results Window
		# *********************************************************************
		
		self.quizresultsview = self.wTree.get_widget("quizresultsview")
		self.quizresultsstore = gtk.TreeStore(str, str, str)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Question", renderer, markup = 0)
		column.set_resizable(True)
		column.set_max_width(200)
		self.quizresultsview.append_column(column)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Your Answer", renderer, markup = 1)
		column.set_resizable(True)
		column.set_visible(True)
		self.quizresultsview.append_column(column)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Correct Answer", renderer, markup = 2)
		column.set_resizable(True)
		column.set_visible(True)
		self.quizresultsview.append_column(column)


		# Fill the category lists for both the Edit and Quiz tabs
		self.OnCategoryRefresh()
		# Fill the planner lists for both Learning and Quiz tabs
		self.OnPlannersRefresh()

		# Show the window
		self.window = self.wTree.get_widget("mainwindow")
		self.window.show()

	def OnSword(self, widget = None):
		''' Use diatheke to grab the verse text relating to the reference entered '''

		# Get the relevant widgets
		verse = self.wTree.get_widget("ref")
		text =  self.wTree.get_widget("versetext")
		textbuffer = text.get_buffer()

		verseref = verse.get_text()
		print "Searching for "+verseref

		versetext = commands.getoutput("diatheke -b "+current_translation+" -k "+verseref)
		textbuffer.set_text(strip_text(versetext))

	def OnCategoryRefresh(self, widget=None):
		# Clear the tree
		self.treestore.clear()
		self.quizstore.clear()

		for centre in self.db.cat_list():
			iter = self.treestore.insert_before(None, None)
			iter2 = self.quizstore.insert_before(None, None)
			self.treestore.set_value(iter, 0, centre['title'])
			self.quizstore.set_value(iter2, 0, centre['title'])
			for item in self.db.verse_list(centre['ref']):
				iter2 = self.treestore.insert_before(iter, None)
				self.treestore.set_value(iter2, 0, item[0])
				self.treestore.set_value(iter2, 1, item[1])

			# Add to the dropdown box too
			self.cat_dropdown.append_text(centre['title'])

		self.cat_dropdown.remove_text(0)
		self.catview.set_model(self.treestore)
		self.catview.show()

		self.quizview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
		self.quizview.set_model(self.quizstore)
		self.quizview.show()

	def OnPlannersRefresh(self, widget=None):
		# Setup the tree view

		# Clear the tree
		self.plannerstore.clear()

		# Clear the dropdown (need to work on this)
		#self.quizplannerdropdown.

		for planner in self.db.planner_list():
			iter = self.plannerstore.insert_before(None, None)
			self.plannerstore.set_value(iter, 0, planner)

			# Add to dropdown too
			self.quizplannerdropdown.append_text(planner)

		self.plannerview.set_model(self.plannerstore)
		self.plannerview.show()
		# Remove the 0 item from the dropdown
		self.quizplannerdropdown.remove_text(0)

	def OnAdd(self, widget=None):
		''' Add or update a verse in the database '''
		if (self.verseid == 0):
			print "Adding verse"
			# Gather the data
			verse = self.wTree.get_widget("ref")
			text =  self.wTree.get_widget("versetext")
			textbuffer = text.get_buffer()
			category = self.cat_dropdown.get_active_text()

			# Add to the database
			# Check the category exists - if not then query creation
			if not (category in self.db.cat_list(False)):
				msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO, "The category '"+category+"' does not exist. Would you like to create it?")
				resp = msg.run()
				if resp == gtk.RESPONSE_YES:
					msg.destroy()
					# Add category
					self.db.add_category(category)
				else:
					msg.destroy()
					msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK, "Cancelled adding verse")
					resp = msg.run()
					msg.destroy()
					return

			# Add the verse
			self.db.add_verse(verse.get_text(),textbuffer.get_text(textbuffer.get_start_iter(), textbuffer.get_end_iter()),category)

			# Refresh the category list
			self.OnCategoryRefresh()

			# Confirm to the user
			msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK, "Added verse")
			resp = msg.run()
			msg.destroy()
			

	def OnDelete(self, widget=None):
		''' Delete a verse from the database '''
		print "Deleting verse"
		if self.verseid == 0:
			print "Verse not selected"
			msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, "You need to select a verse first.")
			resp = msg.run()
			msg.destroy()
		else:
			msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO, "Do you really wish to delete this memory verse?")
			resp = msg.run()
			if resp == gtk.RESPONSE_YES:
				self.db.delete_verse(self.verseid)
				print "Deleted verse "+self.verseid
				self.OnCategoryRefresh()
				self.OnClear()
			msg.destroy()

	def OnClear(self, widget=None):
		''' Clear the form '''
		print "Clearing..."
		# Get the widgets
		verse = self.wTree.get_widget("ref")
		text =  self.wTree.get_widget("versetext")
		textbuffer = text.get_buffer()
		
		# Clear them
		textbuffer.set_text("")
		verse.set_text("")

		# Clear the dropdown
		# This is a bit of a kludge as -1 doesn't work with ComboBoxEntry
		self.cat_dropdown.insert_text(0, "")
		self.cat_dropdown.set_active(0)
		self.cat_dropdown.remove_text(0)

		# Clear the verseid
		self.verseid = 0

		# Set the add button back to add (in case we've been updating)
		addbutton = self.wTree.get_widget("addbutton")
		addbutton.set_label("gtk-add")
	

	def OnLoadVerse(self, widget, path, column):
		''' Load a verse from the category tree into the view '''
		print "Loading verse"

		if (self.treestore.iter_parent(self.treestore.get_iter(path))):
			# If we have a parent (ie it's a verse, not a category)
			verseref = self.treestore.get_value(self.treestore.get_iter(path), 0)
			self.verseid = self.treestore.get_value(self.treestore.get_iter(path), 1)
			print "verse id = "+self.verseid
			# Load the verse into the textbox, and hit the sword button
			versebox = self.wTree.get_widget("ref")
			versebox.set_text(verseref)
			button = self.wTree.get_widget("swordbutton")
			button.clicked()

			# Put the category in the dropdown
			category = self.treestore.get_value(self.treestore.iter_parent(self.treestore.get_iter(path)), 0)
			# This is kludgy and needs to be better
			counter = 0			
			for loop in range(len(self.db.cat_list())):
				self.cat_dropdown.set_active(loop)
				if (self.cat_dropdown.get_active_text() == category):
					counter = loop

			self.cat_dropdown.set_active(counter)

			# Set add button to update
			addbutton = self.wTree.get_widget("addbutton")
			addbutton.set_label("Update")	
		else:
			# We have no parent, thus we're a category
			print "Just a category"

	def OnChangePage(self, widget, page, pagenum):
		''' When the user switches to another page '''

		print "Page changed to page number "+str(pagenum)
		if (pagenum == 1 and len(self.db.planner_list()) == 0):
			print "No planners - offer creation wizard"
			msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, "There are no learning planners. Would you like me to create one now?")
			resp = msg.run()
			msg.destroy()
			if resp == gtk.RESPONSE_YES:
				self.OnPlannerWizard()
		elif (pagenum == 1):
			# Learn page, but we have planners
			self.wTree.get_widget("plannerexpander").set_expanded(False)
			self.OnLoadPlanner(planner="Test Weekly")

			
	def OnSliderChange(self, widget = None):
		''' Adjust the verse output to match the chosen level '''

		new_level = self.slider.get_value()
		print "Slider changed to "+str(new_level)

		### DAMN - need to fix this and the handling of the question as a whole to incorporate the ability to load verses ###
		todays_verse = self.db.todays_verse(self.default_planner, self.planner_date)
		question = todays_verse[1]

		# Work out how many words (and which) to hide
		num_words = len(self.word_list)
		hide = int((num_words/self.levels)*new_level)
		print "Hiding "+str(hide)+" words"
		for loop in range(hide):
			question = re.sub("\W"+self.word_list[loop]+"\W", " "+stars(self.word_list[loop])+" ", question)

		if (new_level) > (self.levels/2):
			ref = "**** ** : **"
		else:
			ref = todays_verse[0]
		
		# Markup the verse and display
		font = pango.FontDescription("Arial 18")
		self.learn_text.modify_font(font)
		font = pango.FontDescription("Arial 14")
		self.learn_ref.modify_font(font)
		self.learn_text.set_markup(question)
		self.learn_ref.set_markup("<i>"+ref+"</i>")

		# Load up the editor
		self.show_verse.set_text(todays_verse[0])
		self.show_cat.set_text(self.db.get_cat_from_verse(todays_verse[0]))
		self.show_text.set_text(todays_verse[1])

	def OnSliderButton(self, widget=None):
		''' Adjust the slider with buttons instead '''

		# Work out which button
		change = [0, self.slider.get_value()-1, self.slider.get_value()+1, self.levels]
		options = ['homebutton', 'lessbutton', 'morebutton', 'endbutton']

		change_val = change[options.index(widget.get_name())]

		# Adjust the slider accordingly
		self.slider.set_value(change_val)

	def OnPlannerWizard(self, widget=None):
		''' Show the planner wizard '''
		print "Planner creation"
		plannertree = gtk.glade.XML(self.gladefile, "plannerwizard")
		dic = {
				'on_planner_cancel_clicked' : self.OnPlannerCancel,
				'on_planner_ok_clicked' : self.OnPlannerOK,
				}
		plannertree.signal_autoconnect(dic)
		self.wizard = plannertree.get_widget("plannerwizard")
		self.freqdropdown = plannertree.get_widget("freqdropdown")
		self.calendar = plannertree.get_widget("calendar2")
		self.plannername = plannertree.get_widget("entry1")

		# Setup the treeview
		self.plannercatview = plannertree.get_widget("catview")
		self.plannercatview.set_level_indentation(0)
		self.plannercatstore = gtk.TreeStore(str, str)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Category", renderer, markup = 0)
		column.set_resizable(True)
		self.plannercatview.append_column(column)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("DBID", renderer, markup = 0)
		column.set_resizable(True)
		column.set_visible(False)
		self.plannercatview.append_column(column)

		# Clear the tree
		self.plannercatstore.clear()

		for category in self.db.cat_list():
			iter = self.plannercatstore.insert_before(None, None)
			self.plannercatstore.set_value(iter, 0, category['title'])
			self.plannercatstore.set_value(iter, 1, category['ref'])

		self.plannercatview.set_model(self.plannercatstore)

		self.plannercatview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
		self.plannercatview.show()

		self.wizard.show()

	
	def OnPlannerCancel(self, widget=None):
		''' Cancel the planner wizard '''
		self.wizard.destroy()

	def OnPlannerOK(self, widget=None):
		''' Confirm the planner creation '''

		selection = self.plannercatview.get_selection()

		# Check that they've selected some categories
		if selection.count_selected_rows() == 0:
			msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, "You need to select some categories first.")
			resp = msg.run()
			msg.destroy()
			self.wizard.present()
			return
		else:
			selected_cats = self.plannercatview.get_selection().get_selected_rows()[1]
			# Count the number of verses in these categories
			# Convert the paths into DBIDs
			selected_cat_list = []
			for cat in selected_cats:
				tempid = self.plannercatstore.get_value(self.plannercatstore.get_iter(cat), 1)
				selected_cat_list.append(tempid)

			# Check against database
			versecount = self.db.verse_count(selected_cat_list)
			catcount = selection.count_selected_rows()

			# Get the frequency and calculate the number of days
			frequency = self.freqdropdown.get_active()

			# Note - Daily, Bi-Weekly, Weekly, Fortnightly, Monthly
			multiplier = [1, 3, 7, 14, 30]
			duration = versecount * multiplier[frequency]

			# Create a more easily readable duration
			if (duration < 60):
				dur_text = str(duration)+" days."
			elif (duration < 140):
				dur_text = str(duration/7)+" weeks."
			else:
				dur_text = str(duration/30)+" months."

			# Confirm with the user
			msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_YES_NO, "You have selected "+str(catcount)+" categories containing "+str(versecount)+" memory verses, taking approximately "+dur_text+"\nDo you wish to continue?")
			resp = msg.run()
			msg.destroy()
			if resp == gtk.RESPONSE_NO:
				self.wizard.present()
				return
			else:
				print "continuing"
				# Insert appropriate dates and verses into the database
				# Bi-Weekly should be start_day and start_day + 3 every week (ie Monday and Thursday)
				# Weekly should be same day every week
				# Fortnightly should be the same day every fornight
				# Monthly should be the same numerical day each month

				# Get the start date
				year, month, day = self.calendar.get_date()
				month += 1
				start_date = datetime.date.today()
				start_date = start_date.replace(year, month, day)
				day_counter = multiplier[frequency]

				# Handle daily, bi-weekly weekly and fortnightly here
				if frequency in [0, 1, 2, 3]:
					increment = multiplier[frequency]
					tempdate = start_date
					for category in selected_cat_list:
						for verse in self.db.verse_list(category):
							self.db.add_verse_to_planner(self.plannername.get_text(), verse[1], tempdate.isoformat())
							tempdate = start_date + datetime.timedelta(days=day_counter)
							day_counter += increment
							# Handle bi-weekly
							if frequency == 1:
								if increment == 3:
									increment = 4
								else:
									increment = 3
					# Add in a dummy end date
					self.db.add_verse_to_planner(self.plannername.get_text(), "END", tempdate.isoformat())
				else:
					# Monthly
					tempdate = start_date
					tempmonth = month
					tempyear = year
					for category in selected_cat_list:
						for verse in self.db.verse_list(category):
							self.db.add_verse_to_planner(self.plannername.get_text(), verse[1], tempdate.isoformat())
							tempmonth += 1
							if tempmonth == 13:
								tempmonth = 1
								tempyear += 1
							tempdate = tempdate.replace(tempyear, tempmonth, day)	
					# Add in a dummy end date
					self.db.add_verse_to_planner(self.plannername.get_text(), "END", tempdate.isoformat())
				self.OnPlannersRefresh()
				self.wizard.destroy()

	def OnLoadPlanner(self, widget=None, path=None, column=None, planner="Test Weekly"):
		''' Load a planner into the learn tab '''
		if (widget != None):
			# Get from the selection widget
			self.default_planner = self.plannerstore.get_value(self.plannerstore.get_iter(path), 0)
		#else:
			#self.default_planner = planner

		print "Using planner "+self.default_planner
		todays_verse = self.db.todays_verse(self.default_planner, self.planner_date)
		print todays_verse
		if (todays_verse != -1):
			# **************************************
			# Calculate any 'distortions' required
			# **************************************
			
			# Work out the dates
			last, next = self.db.next_and_last(self.default_planner, self.planner_date)			
			if (-1 not in [last,next]):
				lastdate = datetime.datetime.strptime(last, '%Y-%m-%d')
				nextdate = datetime.datetime.strptime(next, '%Y-%m-%d')
				days_in_cycle = nextdate-lastdate
				days_in_cycle = days_in_cycle.days
				if (self.planner_date == 'now'):
					days_complete = datetime.datetime.today()-lastdate
				else:
					days_complete = datetime.datetime.strptime(self.planner_date, '%Y-%m-%d')-lastdate
				days_complete = days_complete.days

				if (days_in_cycle < 10):
					self.levels = days_in_cycle
					self.days_per_level = 1
				else:
					self.levels = 10
					self.days_per_level = days_in_cycle/10

				print "Setting levels to "+str(self.levels)+" and days per level to "+str(self.days_per_level)

				# Strip out punctuation from the verse and generate wordlist
				temp = todays_verse[1]
				question = todays_verse[1]
				for punc in string.punctuation:
					temp = temp.replace(punc, " ")
				self.word_list = temp.split()

				# Sort by length
				self.word_list.sort(cmp=bylength)

				# Work out how many words (and which) to hide
				num_words = len(self.word_list)
				print "Num words = "+str(num_words)
				print "days complete = "+str(days_complete)
				hide = int((num_words/self.levels)*(days_complete/self.days_per_level))
				print "Hiding "+str(hide)+" words"
				for loop in range(hide):
					question = re.sub("\W"+self.word_list[loop]+"\W", " "+stars(self.word_list[loop])+" ", question)

				if (self.levels - (self.days_per_level * days_complete)) <= (self.levels / 2) :
					ref = "**** ** : **"
				else:
					ref = todays_verse[0]
				
				# Markup the verse and display
				font = pango.FontDescription("Arial 18")
				self.learn_text.modify_font(font)
				font = pango.FontDescription("Arial 14")
				self.learn_ref.modify_font(font)
				self.learn_text.set_markup(question)
				self.learn_ref.set_markup("<i>"+ref+"</i>")

				# Adjust the slider
				self.slider.set_range(0, self.levels)
				self.slider.set_value(days_complete / self.days_per_level)

				# Load up the editor
				self.show_verse.set_text(todays_verse[0])
				self.show_cat.set_text(self.db.get_cat_from_verse(todays_verse[0]))
				self.show_text.set_text(todays_verse[1])

		# Mark the calendar
		calendar = self.wTree.get_widget("calendar1")
		calendar.clear_marks()
		year, month, day = calendar.get_date()
		date_list = self.db.get_planner_dates(self.default_planner, string.zfill(str(month+1),2), str(year))
		for day in date_list:
			calendar.mark_day(int(day))

	def OnPlannerDateChange(self, widget=None):
		''' Date is changed - reload the planner '''

		year, month, date = widget.get_date()
		mydate = str(year)+"-"+string.zfill(str(month+1),2)+"-"+string.zfill(str(date),2)
		print "Selected "+mydate
		self.planner_date = mydate
		self.OnLoadPlanner()

	def OnPlannerMonthChange(self, widget=None):
		''' Month has changed - update the marks on the calendar '''
		widget.clear_marks()
		year, month, date = widget.get_date()
		date_list = self.db.get_planner_dates(self.default_planner, string.zfill(str(month+1), 2), str(year))
		for day in date_list:
			widget.mark_day(int(day))

	def Preferences(self, widget=None):
		''' Display the preferences dialog, and handle output '''
		global current_translation
		global current_planner
		prefTree = gtk.glade.XML(self.gladefile, "prefs")
		dlg = prefTree.get_widget("prefs")

		pref_translation = prefTree.get_widget("translation_dropdown")
		pref_planner = prefTree.get_widget("planner_dropdown")

		translations = get_translations_from_sword()
		for translation in translations:
			pref_translation.append_text(translation[0]+" : "+translation[1])
		pref_translation.remove_text(0)
		for loop in range(len(translations)):
			if (translations[loop][0] == current_translation):
				pref_translation.set_active(loop)

		planner_list = self.db.planner_list()
		for tempplanner in planner_list:
			pref_planner.append_text(tempplanner)
		pref_planner.remove_text(0)
		for loop in range(len(planner_list)):
			if (planner_list[loop] == current_planner):
				pref_planner.set_active(loop)

		result = dlg.run()
		dlg.destroy()
		if (result == gtk.RESPONSE_OK):
			print "saving preferences"
			translation = pref_translation.get_active_text()
			translation = translation.split(" : ")[0]
			newplanner = pref_planner.get_active_text()

			config.set('Section1','translation',translation)
			config.set('Section1','default_planner',newplanner)
			with open(os.path.join(config_path, '.whetstone'), 'wb') as configfile:
				config.write(configfile)
			current_translation = translation
			current_planner = newplanner

	def OnQuizLaunch(self, widget=None):
		''' Analyse the quiz tab fields and launch the appropriate quiz '''

		quiz_type = self.wTree.get_widget("quiztypedropdown").get_active()
		if (quiz_type == -1):
			# Nothing selected
			msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, "Please select a quiz type before continuing.")
			msg.run()
			msg.destroy()
			return

		quiz_types = ['Verse', 'Ref', 'Words', 'Whole']
		quiz_type = quiz_types[quiz_type]

		if (widget.get_name() == "categoryquiz"):
			# Get a list of verse IDs based on the selected categories
			verselist = []
			selected_cats = self.quizview.get_selection().get_selected_rows()[1]
			if not (selected_cats):
				# Need to select some categories
				msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, "Please select 1 or more categories before continuing.")
				msg.run()
				msg.destroy()
				return
			for cat in selected_cats:
				tempcat = self.quizstore.get_value(self.quizstore.get_iter(cat), 0)
				tempid = self.db.get_category_id(tempcat)
				tempverselist = self.db.verse_list(catref=tempid)
				for verse in tempverselist:
					verselist.append(verse[1])

		if (widget.get_name() == "plannerquiz"):
			# Get the name of the planner and the quiz limit
			planner = self.wTree.get_widget("quizplannerdropdown").get_active_text()
			limit = self.wTree.get_widget("quizplannerlimit").get_active()
			if (planner == -1 or limit == -1):
				# Need to select something from both dropdowns
				msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, "Please select a planner and verses before continuing.")
				msg.run()
				msg.destroy()
				return

			limit = limit*4
			# Get a list of verse IDs from the planner
			verselist = self.db.get_verselist_todate(planner=planner, limit=limit)
			

		if (quiz_type in ['Verse', 'Ref', 'Words']):
			self.OnMultiQuiz(type=quiz_type, verselist = verselist)	

	def OnMultiQuiz(self, widget=None, type='Verse', verselist=[1]):
		''' Display a multiple-choice quiz '''
		# Verselist should be a list of verse DB IDs

		# Generate list of dictionaries of questions, format:
		# [{question="For God so Loved the world", a="Revelation 21:21", b="Matthew 4:4", c="John 3:16", d="Genesis 1:1", answer="c"}]

		self.quiz = []
		choices = ['a','b','c','d']
		for verse in verselist:
			temp = self.db.get_verse(verse)
			if (type == "Verse"):
				tempq = temp[1]
				tempa = [temp[0]]
				answer = temp[0]
			elif (type == "Ref"):
				tempq = temp[0]
				tempa = [temp[1]]
				answer = temp[1]
			wrongs = self.db.get_random_verses(3, type, verse)
			for item in wrongs:
				tempa.append(item)
			# randomise the list
			tempa = random.sample(tempa, 4)
			self.quiz.append({'question':tempq, 'a':tempa[0], 'b':tempa[1], 'c':tempa[2], 'd':tempa[3], 'answer':choices[tempa.index(answer)]})

		# randomise the quiz questions
		self.quiz = random.sample(self.quiz, len(self.quiz))

		# Store the users answers
		self.quizanswers = []
		for item in self.quiz:
			self.quizanswers.append('')

		# Launch the quiz window
		self.quizwindow = self.wTree.get_widget("multiquiz")
		self.quizwindow.connect("delete-event", self.OnQuizQuit)
		self.quizpos = 0
		self.OnQuizButton()

		self.quizwindow.show()

	def ShowQuizPage(self, widget = None):
		''' Show the relevant page of a quiz '''
		self.quizquestion = self.wTree.get_widget("question")
		self.quiza = self.wTree.get_widget("choicea")
		self.quizb = self.wTree.get_widget("choiceb")
		self.quizc = self.wTree.get_widget("choicec")
		self.quizd = self.wTree.get_widget("choiced")

		# Load in the question
		font = pango.FontDescription("Arial 18")
		self.quizquestion.modify_font(font)
		self.quizquestion.set_markup(self.quiz[self.quizpos]['question'])

		# Load in the answers
		self.quiza.set_label(ellipsize(self.quiz[self.quizpos]['a']))
		self.quizb.set_label(ellipsize(self.quiz[self.quizpos]['b']))
		self.quizc.set_label(ellipsize(self.quiz[self.quizpos]['c']))
		self.quizd.set_label(ellipsize(self.quiz[self.quizpos]['d']))

		#self.quiza.set_line_wrap(True)
		#self.quizb.set_line_wrap(True)
		#self.quizc.set_line_wrap(True)
		#self.quizd.set_line_wrap(True)

		# Adjust the statusbar
		status = "Question "+str(self.quizpos+1)+" out of "+str(len(self.quiz))
		self.wTree.get_widget("quizstatus").push(-1, status)

		# Activate the correct answer from previous choices
		if (self.quizanswers[self.quizpos] == "a"):
			self.quiza.set_active(True)
		elif (self.quizanswers[self.quizpos] == "b"):
			self.quizb.set_active(True)
		elif (self.quizanswers[self.quizpos] == "c"):
			self.quizc.set_active(True)
		elif (self.quizanswers[self.quizpos] == "d"):
			self.quizd.set_active(True)
		else:
			self.quiza.set_active(False)
			self.quizb.set_active(False)
			self.quizc.set_active(False)
			self.quizd.set_active(False)


	def OnQuizButton(self, widget=None):
		''' Move to the appropriate page in the quiz '''
		if (widget == None):
			self.quizpos = 0
		elif (widget.get_name() == 'quizfirst'):
			self.quizpos = 0
		elif (widget.get_name() == 'quizback'):
			self.quizpos -= 1
			if (self.quizpos == -1):
				self.quizpos = 0
		elif (widget.get_name() == 'quiznext'):
			self.quizpos += 1
			if (self.quizpos > len(self.quiz)-1 ):
				self.quizpos = len(self.quiz)-1
		else:
			self.quizpos = len(self.quiz)-1

		# Update the buttons
		if (self.quizpos == 0):
			# Disable First and Back buttons, enable Last and Next
			self.wTree.get_widget("quizfirst").set_sensitive(False)
			self.wTree.get_widget("quizback").set_sensitive(False)
			self.wTree.get_widget("quiznext").set_sensitive(True)
			self.wTree.get_widget("quizlast").set_sensitive(True)
		elif (self.quizpos > 0) and (self.quizpos < len(self.quiz)-1):
			# Enable everything
			self.wTree.get_widget("quizfirst").set_sensitive(True)
			self.wTree.get_widget("quizback").set_sensitive(True)
			self.wTree.get_widget("quiznext").set_sensitive(True)
			self.wTree.get_widget("quizlast").set_sensitive(True)
		elif (self.quizpos == len(self.quiz)-1):
			# Disable Next and Last
			self.wTree.get_widget("quizfirst").set_sensitive(True)
			self.wTree.get_widget("quizback").set_sensitive(True)
			self.wTree.get_widget("quiznext").set_sensitive(False)
			self.wTree.get_widget("quizlast").set_sensitive(False)

		self.ShowQuizPage()

	def OnQuizAnswer(self, widget):
		''' Store the answer selected '''
		self.quizanswers[self.quizpos] = widget.get_name()[-1]
		print self.quizanswers

	def OnQuizFinish(self, widget):
		''' Output the results for the user '''
		# Check that they've filled in answers for everything
		if ("" in self.quizanswers):
			msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, "Please choose an answer for every question")
			msg.run()
			msg.destroy()
			return			
		self.quizwindow.hide()
		# Calculate the number of correct answers
		correct = 0
		for answer in range(len(self.quizanswers)):
			if (self.quizanswers[answer] == self.quiz[answer]['answer']):
				correct += 1

		# Setup the quiz results dialog
		result = "You got "+str(correct)+" correct out of a possible "+str(len(self.quizanswers))
		self.wTree.get_widget("score").set_label(result)

		# Populate the treeview
		# Clear the tree
		self.quizresultsstore.clear()

		for question in range(len(self.quiz)):
			iter = self.quizresultsstore.insert_before(None, None)
			self.quizresultsstore.set_value(iter, 0, self.quiz[question]['question'])
			if (self.quiz[question]['answer'] == self.quizanswers[question]):
				mycolour = "green"
			else:
				mycolour = "red"
			self.quizresultsstore.set_value(iter, 1, "<span foreground='"+mycolour+"'>"+self.quizanswers[question] + " : "+self.quiz[question][self.quizanswers[question]]+"</span>")
			self.quizresultsstore.set_value(iter, 2, "<span foreground='green'>"+self.quiz[question]['answer'] + " : "+self.quiz[question][self.quiz[question]['answer']]+"</span>")

		self.quizresultsview.set_model(self.quizresultsstore)

		self.quizresultsview.show()

		quizresultsdialog = self.wTree.get_widget('results')
		quizresultsdialog.connect("delete-event", self.OnResultsFinish)
		quizresultsdialog.show()

	def OnQuizQuit(self, widget=None, event=None):
		''' Hide the window if destroyed, rather than killing it '''
		widget.hide()
		return True

	def OnResultsFinish(self, widget=None, event=None):
		# Hide the results window
		window = self.wTree.get_widget("results")
		window.hide()
		return True

	def About(self, widget=None):
		''' Display the About dialog '''
		aboutTree = gtk.glade.XML(self.gladefile, "aboutdialog1")
		dlg = aboutTree.get_widget("aboutdialog1")
		dlg.run()
		dlg.destroy()
		
	def OnQuit(self, widget=None):
		gtk.main_quit()



if __name__ == "__main__":
	app = guiClient()
	gtk.main()
