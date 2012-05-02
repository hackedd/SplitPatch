import re
import sys

class PatchSet:
	NO_NEWLINE = "\\ No newline at end of file"
	lineInfoRegex = re.compile(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@")

	def __init__(self, patchData):
		self.patches = {}
		self._read_string(patchData)

	def _read_string(self, patchData):
		"""
		Reads a (unified) patch from input string.
		Returns a dictionary with the filenames as keys, and the list of hunks
		as values. Hunks contain information about the starting line number in
		the original and modified files, as well as the number of lines in the
		modified by the hunk. They also contain the original and modfied lines.
		"""

		lines = patchData.splitlines()
		numLines = len(lines)
		line = 0

		while line < numLines:
			# process Index:
			filename = lines[line][7:]

			if not filename in self.patches:
				patch = Patch(filename)
				patch.line = line
				self.patches[filename] = patch
			else:
				patch = self.patches[filename]

			line += 1
			# skip divider
			line += 1
			# skip original filename (if present)
			if lines[line].startswith("--- "): line += 1
			# skip modified filename (if present)
			if lines[line].startswith("+++ "): line += 1

			while line < numLines and not lines[line].startswith("Index: "):
				if not lines[line].startswith("@@ "):
					# invalid hunk, skip to next Index
					startLine = line
					while line < numLines and not lines[line].startswith("Index: "):
						line += 1

					hunk = Hunk(patch)
					hunk.lines = lines[startLine:line]
					hunk.invalid = True
					patch.append(hunk)

					continue

				lineInfo = self.lineInfoRegex.match(lines[line])
				if not lineInfo:
					raise Exception("Unable to parse patch. Expected '@@'; got '%s' on line %d" % (lines[line], line + 1))

				hunk = Hunk(patch)
				hunk.lineInfo = lines[line]
				hunk.originalLineStart = int(lineInfo.group(1))
				hunk.originalNumLines  = int(lineInfo.group(2))
				hunk.modifiedLineStart = int(lineInfo.group(3))
				hunk.modifiedNumLines  = int(lineInfo.group(4))

				line += 1
				startLine = line
				while line < numLines and (not lines[line] or lines[line][0] in (" ", "-", "+")):
					line += 1

				hunk.lines = lines[startLine:line]

				if line < numLines and lines[line] == self.NO_NEWLINE:
					hunk.noNewline = True
					line += 1

				patch.append(hunk)

	def iteritems(self):
		return self.patches.iteritems()

	def write(self, fp = sys.stdout):
		for filename, patch in self.iteritems():
			patch.write(fp)

class Patch:
	def __init__(self, filename):
		self.filename = filename
		self.line = None
		self.hunks = []

	def append(self, hunk):
		self.hunks.append(hunk)

	def __len__(self):
		return len(self.hunks)

	def write(self, fp = sys.stdout):
		included = filter(lambda h: h.include, self.hunks)
		if len(included) == 0:
			return

		print >>fp, "Index: %s" % self.filename
		print >>fp, "=" * 67
		print >>fp, "--- %s" % self.filename
		print >>fp, "+++ %s" % self.filename

		for hunk in self.hunks:
			# TODO: re-calculate lineInfo offsets
			print >>fp, hunk.lineInfo
			print >>fp, "\n".join(hunk.lines)
			if hunk.noNewline:
				print >>fp, PatchSet.NO_NEWLINE

class Hunk:
	def __init__(self, patch = None):
		self.patch = patch
		self.lineInfo = None
		self.originalLineStart = self.originalNumLines = None
		self.modifiedLineStart = self.modifiedNumLines = None
		self.lines = []
		self.noNewline = False
		self.invalid = False
		self.include = True
