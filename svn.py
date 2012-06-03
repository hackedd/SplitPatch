import os
import sys

from subprocess import Popen, PIPE
from tempfile import TemporaryFile

from patch import PatchSet

class ProcessException(Exception):
	def __init__(self, command, returncode):
		Exception.__init__(self, "%s exited with code %d" % (command, returncode))
		self.command = command
		self.returncode = returncode

def run_command(*args):
	command = Popen(args, stdout = PIPE, stderr = PIPE)
	output, errors = command.communicate()
	if command.returncode:
		print >>sys.stderr, "stdout:", output
		print >>sys.stderr, "stderr:", errors
		raise ProcessException(" ".join(args), command.returncode)
	return output

def run_command_with_input(stdin, *args):
	if isinstance(stdin, basestring):
		command = Popen(args, stdin = PIPE, stdout = PIPE, stderr = PIPE)
		output, errors = command.communicate(stdin)
	else:
		command = Popen(args, stdin = stdin, stdout = PIPE, stderr = PIPE)
		output, errors = command.communicate()

	if command.returncode:
		print >>sys.stderr, "stdout:", output
		print >>sys.stderr, "stderr:", errors
		raise ProcessException(" ".join(args), command.returncode)
	return output

def get_svn_diff(input):
	workingDir = os.getcwd()
	try:
		os.chdir(input)
		output = run_command("svn", "diff")
		return PatchSet(output)
	except ProcessException, ex:
		raise Exception("svn diff exited with code %d" % ex.returncode)
	finally:
		os.chdir(workingDir)

def do_partial_commit(wc, patchset, message, progress = None):
	"""
	Attempts a partial SVN commit to given working copy (using message) as the
	commit message. progress is a callable accepting a status message to display
	to the user, and a flag that will be set upon completion.
	"""

	# Make sure progess is callable
	if progress == None: progress = lambda msg, done: None

	state = None

	try:
		workingDir = os.getcwd()
		os.chdir(wc)

		included = TemporaryFile(suffix = "included.patch")
		patchset.write(included)
		included.seek(0)

		excluded = TemporaryFile(suffix = "excluded.patch")
		patchset.write_excluded(excluded)
		excluded.seek(0)

		progress("Reverting all changes in '%s'..." % wc, False)
		print >>sys.stderr, "svn revert:"
		print >>sys.stderr, run_command("svn", "revert", "--non-interactive", "--depth=infinity", ".")
		state = "revert"

		progress("Re-Applying selected patches...", False)
		print >>sys.stderr, "patch (included)"
		print >>sys.stderr, run_command_with_input(included, "patch", "-p0", "--verbose")
		state = "included"

		progress("running 'svn commit'", False)
		print >>sys.stderr, "svn commit"
		print >>sys.stderr, run_command_with_input(message, "svn", "commit", "--non-interactive", "--file", "-")
		state = "commit"

		progress("Re-Applying remaining patches", False)
		print >>sys.stderr, "patch (excluded)"
		print >>sys.stderr, run_command_with_input(excluded, "patch", "-p0", "--verbose")
		state = "done"

		progress("Done", True)

	except Exception, ex:
		if state and state != "done":
			try:
				if state == "revert":
					progress("Re-Applying patches", False)
					print >>sys.stderr, "patch (included)"
					print >>sys.stderr, run_command_with_input(included, "patch", "-p0", "--verbose")
				if state == "revert" or state == "commit":
					progress("Re-Applying patches", False)
					print >>sys.stderr, "patch (excluded)"
					print >>sys.stderr, run_command_with_input(excluded, "patch", "-p0", "--verbose")
			except Exception, ex2:
				progress(Exception("%s (%s)" % (ex2, ex)), True)
		else:
			progress(ex, True)

	finally:
		os.chdir(workingDir)
