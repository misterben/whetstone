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



# v0.0.1
# Requires Diatheke and the ESV bible module to be installed

import sys, commands, re, datetime, string
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


diatheke_test = commands.getoutput("which diatheke")
if (diatheke_test == ""):
	print "Unable to locate diatheke; you will not be able to pull scripture verses"
else:
	print "Located diatheke at "+diatheke_test


from pysqlite2 import dbapi2 as sqlite

# Static translation to start with; need to add this to the preferences.
tr = "ESV"

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
					versetext = strip_text(commands.getoutput("diatheke -b "+tr+" -k "+verse))
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
		return [raw_result[0][0], raw_result[0][1], raw_result[0][2]]

	def next_and_last(self, planner, date='now'):
		''' Return the previous and next dates on the given planner, in the format [last,next] '''
		self.cur.execute("SELECT date FROM planner WHERE date <= date('"+date+"') AND name = '"+planner+"' ORDER BY date DESC LIMIT 1")
		last = self.cur.fetchall()[0][0]
		self.cur.execute("SELECT date FROM planner WHERE date > date('"+date+"') AND name = '"+planner+"' ORDER BY date ASC LIMIT 1")
		next = self.cur.fetchall()[0][0]
		return [last, next]

	def get_planner_dates(self, planner, month, year):
		''' Return a list of all the dates in the planner for a given month '''
		self.cur.execute("SELECT strftime('%d',date) FROM planner WHERE name='"+planner+"' and strftime('%m-%Y', date) = '"+month+"-"+year+"'")
		raw_dates = self.cur.fetchall()
		date_list = []
		for item in raw_dates:
			date_list.append(item[0])
		return date_list

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

		self.OnCategoryRefresh()

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

		versetext = commands.getoutput("diatheke -b "+tr+" -k "+verseref)
		textbuffer.set_text(strip_text(versetext))

	def OnCategoryRefresh(self, widget=None):
		# Setup the tree view

		# Clear the tree
		self.treestore.clear()

		for centre in self.db.cat_list():
			iter = self.treestore.insert_before(None, None)
			self.treestore.set_value(iter, 0, centre['title'])
			for item in self.db.verse_list(centre['ref']):
				iter2 = self.treestore.insert_before(iter, None)
				self.treestore.set_value(iter2, 0, item[0])
				self.treestore.set_value(iter2, 1, item[1])

			# Add to the dropdown box too
			self.cat_dropdown.append_text(centre['title'])

		self.cat_dropdown.remove_text(0)
		self.catview.set_model(self.treestore)
		self.catview.show()

	def OnPlannersRefresh(self, widget=None):
		# Setup the tree view

		# Clear the tree
		self.plannerstore.clear()

		for planner in self.db.planner_list():
			iter = self.plannerstore.insert_before(None, None)
			self.plannerstore.set_value(iter, 0, planner)

		self.plannerview.set_model(self.plannerstore)
		self.plannerview.show()

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

		if (new_level) >= 5:
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
				day_counter = 1

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

		# **************************************
		# Calculate any 'distortions' required
		# **************************************
		
		# Work out the dates
		last, next = self.db.next_and_last(self.default_planner, self.planner_date)			
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

		if (self.levels - (self.days_per_level * days_complete)) < 5:
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
