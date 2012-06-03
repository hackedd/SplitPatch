import os
import sys
from argparse import ArgumentParser

from patch import PatchSet
from svn import get_svn_diff

def detect_gui():
	# TODO: Implement actual logic
	return False

def get_patchset(input):
	if input == "-":
		return False, PatchSet(sys.stdin.read())

	if os.path.isfile(input):
		with open(input, "r") as fp:
			return False, PatchSet(fp.read())

	if not os.path.isdir(input):
		raise Exception("'%s' is neither a Patch file nor a directory" % input)

	return True, get_svn_diff(input)

def main():
	parser = ArgumentParser(description = "Split a Patch")
	parser.add_argument("input", metavar = "INPUT", type = str,
		help = "either a patch file or a SVN Working Copy")
	parser.add_argument("--gui", dest = "gui", action = "store_const",
		const = True, default = "auto", help = "display GUI")
	parser.add_argument("--no-gui", dest = "gui", action = "store_const",
		const = False, help = "do not display GUI")

	args = parser.parse_args()

	if args.gui == "auto":
		use_gui = detect_gui()
	else:
		use_gui = args.gui

	if use_gui:
		import gui as interface
	else:
		import cli as interface

	try:
		svn, patchset = get_patchset(args.input)
	except Exception:
		interface.show_error("Unable to read patchset from '%s'" % args.input)
		sys.exit(1)

	if not len(patchset):
		interface.show_error("The patchset '%s' does not contain any patches" % args.input)
		sys.exit(1)

	try:
		interface.show_patchset(svn, args.input, patchset)
	except Exception:
		interface.show_error("Unable to display patchset from '%s'" % args.input)
		sys.exit(1)

	sys.exit(0)
