import sys

def prompt(question, answers = ("yes", "no"), default = None):
	while True:
		print >>sys.stderr, "%s (%s): " % (question, " / ".join(answers)),
		try:
			answer = raw_input()
		except (EOFError, KeyboardInterrupt):
			print >>sys.stderr
			return None

		if not answer and default:
			return default
		if answer in answers:
			return answer
		for option in answers:
			if option.startswith(answer):
				return option

def select_hunks(patch):
	include = prompt("Include %s (%d hunks)" % (patch.filename, len(patch)), ["yes", "no", "partial"], default = "partial")

	if include == None:
		raise SystemExit()
	elif include == "yes":
		pass
	elif include == "no":
		for hunk in patch.hunks:
			hunk.include = False
	else:
		for i, hunk in enumerate(patch.hunks):
			print >>sys.stderr, hunk.lineInfo
			print >>sys.stderr, "\n".join(hunk.lines)
			include = prompt("Include %s (%d / %d)" % (patch.filename, i + 1, len(patch)), default = "yes")
			if include == None: raise SystemExit()
			if include == "no": hunk.include = False

def show_patchset(svn, input, patchset):
	for filename, patch in patchset.iteritems():
		select_hunks(patch)

	patchset.write()

def show_error(message):
	from traceback import print_exc
	print >>sys.stderr, "Error: %s" % message
	print_exc()
