import gtk
import pango
import gobject
import gtksourceview2

from threading import Thread

from main import get_patchset
from patch import Patch, Hunk
from svn import do_partial_commit

def show_patchset(svn, input, patchset):
	gtk.threads_init()

	window = PatchSetWindow(svn, input, patchset)
	window.run()

def show_error(message):
	from traceback import format_exc

	dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
		gtk.BUTTONS_OK, message)

	exception = format_exc()
	if exception:
		dialog.format_secondary_text()

	dialog.run()
	dialog.destroy()

GTK_ROOT_PATH = "0"

class PatchSetWindow(gtk.Window):
	LABEL, OBJECT, INCLUDE, CHECK_VISIBLE = range(4)

	def __init__(self, svn, input, patchset):
		gtk.Window.__init__(self)

		self.svn = svn
		self.input = input
		self.patchset = patchset

		self.set_size_request(750, 550)
		self.set_title("SplitPatch")
		self.connect("delete_event", self.on_delete_event)
		self.connect("destroy", self.on_destroy)

		self._current = None
		self._currentPath = None
		self._treeStore = gtk.TreeStore(str, gobject.TYPE_PYOBJECT, bool, bool)

		self._create_buffer()
		self._create_layout()
		self._fill_tree()

	def _fill_tree(self):
		# determine common prefix (root directory)
		root = _commonprefix(map(lambda f: f.split("/")[:-1], self.patchset.patches.keys()))
		rootLen = len(root)

		# insert root record
		rootIter = self._treeStore.append(None, ("/".join(root), None, False, False))

		for filename, patch in sorted(self.patchset.iteritems()):
			components = filename.split("/")
			path, filename = components[rootLen:-1], components[-1]

			# traverse the current tree, looking for the correct parent record
			parentIter = rootIter
			for component in path:
				childIter = self._treeStore.iter_children(parentIter)
				while childIter != None:
					if self._treeStore[childIter][self.LABEL] == component:
						# name matches, continue with next component
						parentIter = childIter
						break
					childIter = self._treeStore.iter_next(childIter)
				else:
					# parent record not found, create it now
					parentIter = self._treeStore.append(parentIter, (component, None, False, False))

			patchIter = self._treeStore.append(parentIter, (filename, patch, True, True))
			for i, hunk in enumerate(patch.hunks):
				self._treeStore.append(patchIter, ("Hunk %d / %d" % (i + 1, len(patch)), hunk, True, True))

		self._treeView.expand_all()
		self._treeViewSelection.select_path(GTK_ROOT_PATH)

	def _create_layout(self):
		hpaned = gtk.HPaned()
		self.add(hpaned)

		scrolledWindow = gtk.ScrolledWindow()
		scrolledWindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		hpaned.pack1(scrolledWindow, resize = True)

		self._treeView = gtk.TreeView(self._treeStore)
		self._treeViewSelection = self._treeView.get_selection()
		self._treeViewSelection.connect("changed", self.on_selection_changed)
		scrolledWindow.add(self._treeView)

		col = gtk.TreeViewColumn("Name")
		col.set_sort_column_id(self.LABEL)
		col.set_expand(True)
		self._treeView.append_column(col)

		include = gtk.CellRendererToggle()
		include.connect("toggled", self.on_cell_include_toggled)
		col.pack_start(include, expand = False)
		col.set_attributes(include, active = self.INCLUDE, visible = self.CHECK_VISIBLE)

		text = gtk.CellRendererText()
		col.pack_start(text, expand = True)
		col.set_attributes(text, text = self.LABEL)

		vbox = gtk.VBox()
		hpaned.pack2(vbox, resize = True)
		hpaned.set_position(200)

		bbox = gtk.HButtonBox()
		bbox.set_layout(gtk.BUTTONBOX_START)
		vbox.pack_start(bbox, expand = False)

		prev = gtk.Button("Previous")
		prev.connect("clicked", self.on_prev_clicked)
		bbox.pack_start(prev)

		next = gtk.Button("Next")
		next.connect("clicked", self.on_next_clicked)
		bbox.pack_start(next)

		self._include = gtk.CheckButton("Include")
		self._include.connect("clicked", self.on_include_toggled)
		bbox.pack_start(self._include)

		reload_ = gtk.Button("Reload")
		reload_.connect("clicked", self.on_reload_clicked)
		bbox.pack_end(reload_)

		save = gtk.Button("Save Patch")
		save.connect("clicked", self.on_save_clicked)
		bbox.pack_end(save)

		commit = gtk.Button("Commit")
		commit.connect("clicked", self.on_commit_clicked)
		commit.set_sensitive(self.svn)
		bbox.pack_end(commit)

		scrolledWindow = gtk.ScrolledWindow()
		scrolledWindow.set_shadow_type(gtk.SHADOW_IN)
		vbox.pack_start(scrolledWindow, expand = True)

		self._sourceView = gtksourceview2.View(self._buffer)
		self._sourceView.modify_font(pango.FontDescription("monospace 10"))
		scrolledWindow.add(self._sourceView)

		self.show_all()

	def _create_buffer(self):
		lm = gtksourceview2.LanguageManager()
		self._buffer = gtksourceview2.Buffer()
		self._buffer.set_data("languages-manager", lm)

		self._buffer.set_language(lm.get_language("diff"))
		self._buffer.set_highlight_syntax(True)

	def on_delete_event(self, widget, event):
		return False

	def on_destroy(self, widget):
		gtk.main_quit()

	def run(self):
		self.show()
		gtk.main()

	def on_selection_changed(self, selection):
		model, paths = self._treeViewSelection.get_selected_rows()
		if paths:
			self._currentPath = paths[0]
			row = self._treeStore[self._currentPath]
			self.load_hunk(row[self.OBJECT])
		else:
			self.load_hunk(None)

	def load_hunk(self, hunk):
		self._buffer.begin_not_undoable_action()

		if isinstance(hunk, Hunk):
			self._buffer.set_text("\n".join([hunk.lineInfo] + hunk.lines))
		elif isinstance(hunk, Patch):
			patchLines = []
			patch = hunk
			for hunk in patch.hunks:
				patchLines.append(hunk.lineInfo + (" Included" if hunk.include else ""))
				patchLines += hunk.lines
			self._buffer.set_text("\n".join(patchLines))
		else:
			self._buffer.set_text("")

		self._buffer.end_not_undoable_action()
		self._buffer.place_cursor(self._buffer.get_start_iter())

		self._current = hunk
		self._include.set_sensitive(hunk is not None)
		self._include.set_active(hunk is not None and hunk.include)

	def on_prev_clicked(self, widget):
		model, paths = self._treeViewSelection.get_selected_rows()

		if paths:
			prev = paths[0]
			current = self._treeStore.get_iter(paths[0])
			prevIter = iter_prev(current, self._treeStore)
			if not prevIter:
				parentIter = self._treeStore.iter_parent(current)
				if parentIter:
					prevIter = parentIter
			if prevIter:
				prev = self._treeStore.get_path(prevIter)
		else:
			prev = GTK_ROOT_PATH

		self._treeViewSelection.select_path(prev)

	def on_next_clicked(self, widget):
		model, paths = self._treeViewSelection.get_selected_rows()

		if paths:
			next = paths[0]
			current = self._treeStore.get_iter(paths[0])
			if self._treeStore.iter_has_child(current):
				nextIter = self._treeStore.iter_children(current)
			else:
				nextIter = self._treeStore.iter_next(current)
			if nextIter:
				next = self._treeStore.get_path(nextIter)
		else:
			next = GTK_ROOT_PATH

		self._treeViewSelection.select_path(next)

	def on_include_toggled(self, widget):
		self._treeStore[self._currentPath][self.INCLUDE] = self._include.get_active()

	def on_cell_include_toggled(self, widget, path):
		row = self._treeStore[path]
		row[self.INCLUDE] = not row[self.INCLUDE]

		if isinstance(row[self.OBJECT], Hunk):
			row[self.OBJECT].include = not row[self.OBJECT].include
			if row[self.OBJECT] == self._current:
				self._include.set_active(row[self.OBJECT].include)
		elif isinstance(row[self.OBJECT], Patch):
			patch = row[self.OBJECT]
			include = row[self.INCLUDE]

			for hunk in patch.hunks:
				hunk.include = include

			childIter = self._treeStore.iter_children(self._treeStore.get_iter(path))
			while childIter:
				self._treeStore[childIter][self.INCLUDE] = include
				if self._treeStore[childIter][self.OBJECT] == self._current:
					self._include.set_active(include)
				childIter = self._treeStore.iter_next(childIter)

	def on_save_clicked(self, widget):
		dialog = gtk.FileChooserDialog("Save Patch", self, gtk.FILE_CHOOSER_ACTION_SAVE,
			(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		if dialog.run() != gtk.RESPONSE_ACCEPT:
			dialog.destroy()
			return
		filename = dialog.get_filename()
		dialog.destroy()

		try:
			with open(filename, "wb") as fp:
				self.patchset.write(fp)
			dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO,
				gtk.BUTTONS_OK, "Patches written to '%s'" % filename)
			dialog.run()
			dialog.destroy()
		except:
			show_error("Unable to write patches to '%s'" % filename)

	def on_reload_clicked(self, widget = None):
		self.svn, self.patchset = get_patchset(self.input)
		self._treeStore.clear()
		self._fill_tree()

	def on_commit_clicked(self, widget):
		if not self.patchset.included_iteritems():
			show_error("There are no patches to commit.")
			return

		dialog = CommitDialog(self, self.input, self.patchset)
		response = dialog.run()
		dialog.destroy()
		self.on_reload_clicked()

class CommitDialog(gtk.Dialog):
	def __init__(self, parent, wc, patchset):
		gtk.Dialog.__init__(self)

		self.wc = wc
		self.patchset = patchset

		self.set_title("SVN Commit - %s" % wc)
		self.set_size_request(500, 200)

		self._create_layout()

	def _create_layout(self):
		self.vbox.pack_start(gtk.Label("Commit Message"), expand = False)

		self._message = gtk.TextView(gtk.TextBuffer())
		self._message.modify_font(pango.FontDescription("monospace 10"))
		self.vbox.pack_start(self._message)

		self._status = gtk.Label()
		self.vbox.pack_start(self._status, expand = False)

		self._ok = gtk.Button("Commit")
		self._ok.connect("clicked", self.on_ok_clicked)
		self.action_area.pack_start(self._ok)

		self._cancel = gtk.Button("Cancel")
		self._cancel.connect("clicked", self.on_cancel_clicked)
		self.action_area.pack_start(self._cancel)

		self.show_all()

	def on_ok_clicked(self, widget):
		buf = self._message.get_buffer()
		message = buf.get_text(buf.get_start_iter(), buf.get_end_iter())

		if not message:
			dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION,
				gtk.BUTTONS_YES_NO, "You did not specify a log message. Continue anyway?")
			response = dialog.run()
			dialog.destroy()
			if response != gtk.RESPONSE_YES: return

		self._ok.set_sensitive(False)
		self._cancel.set_sensitive(False)
		self._message.set_sensitive(False)

		thread = Thread(target = do_partial_commit,
			args = (self.wc, self.patchset, message, self.on_commit_progress))
		thread.start()

	def on_commit_progress(self, message, done):
		gtk.threads_enter()

		try:
			self._status.set_text(str(message))

			if done:
				if isinstance(message, Exception):
					show_error("Error while comitting changes.")
					self.response(gtk.RESPONSE_REJECT)
				else:
					self.response(gtk.RESPONSE_ACCEPT)
		finally:
			gtk.threads_leave()

	def on_cancel_clicked(self, widget):
		self.response(gtk.RESPONSE_REJECT)

def _commonprefix(items):
	"Given a list of lists, returns the longest common prefix"
	if not items: return []
	minItem, maxItem = min(items), max(items)
	for i, p in enumerate(minItem):
		if p != maxItem[i]:
			return minItem[:i]
	return minItem

def iter_prev(iter, model):
	path = model.get_path(iter)
	position = path[-1]
	if position == 0:
		return None
	prev_path = list(path)[:-1]
	prev_path.append(position - 1)
	prev = model.get_iter(tuple(prev_path))
	return prev
