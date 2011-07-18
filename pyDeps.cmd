@setlocal enableextensions & python -x "%~f0" %* & goto :EOF


try:
	import wingdbstub
except: pass

import os
import sys
import dependencies

from consoleChroma import Warn, Error, Good, setConsoleColour, BRIGHT, FG_WHITE, FG_YELLOW
from filesystem import Path

HELP_ARGS = '-h', '-help', '/h', '/help', '/?'
UPDATE_ARGS = '/u', '/update'
REBUILD_ARGS = '/f', '/force', '/rebuild'
PRINT_TREE_ARGS = '/t', '/tree'
PRINT_DEPENDENTS = '/d', '/dependents'
PRINT_DEPENDENCIES = '/i', '/imports'
PRINT_TESTS_ARGS = '/s', '/tests'
PACKAGE_SCRIPTS = '/p', '/package'


def printHelp():
	print """Prints a list of scripts dependent on the given script/s.  ie: prints
the scripts that directly import the one/s specified on the cmd-line

USAGE: pydeps <flags> someScript.py

	to update the dependency cache:                                          %s
	to rebuild the dependency cache:                                         %s
	to print the dependency tree:                                            %s
	prints dependents (scripts that import this one) [depth, default 0]:     %s
	prints import dependencies [depth, default 1]:                           %s
	prints out the tests that exercise the given scripts                     %s
	packages up the given scripts and all import dependencies into a zip     %s
""" % (' '.join( UPDATE_ARGS ), ' '.join( REBUILD_ARGS ), ' '.join( PRINT_TREE_ARGS ), ' '.join( PRINT_DEPENDENTS ), ' '.join( PRINT_DEPENDENCIES ), ' '.join( PRINT_TESTS_ARGS ), ' '.join( PACKAGE_SCRIPTS ))


def logWarning( *a ):
	print >> Warn, ' '.join( map( str, a ) )

def logHighlight( *a ):
	print >> Good, ' '.join( map( str, a ) )

def logError( *a ):
	print >> Error, ' '.join( map( str, a ) )


#insert the log warning function above into the dependencies namespace so warnings get logged in the appropriate colour
dependencies.logWarning = logWarning


def main():
	args = sys.argv[ 1: ]  #first arg is always this script

	if not args:
		printHelp()
		return

	for arg in HELP_ARGS:
		if arg in args:
			printHelp()
			args.remove( arg )

	updateCache = False
	for arg in UPDATE_ARGS:
		if arg in args:
			updateCache = True
			args.remove( arg )

	rebuild = False
	for arg in REBUILD_ARGS:
		if arg in args:
			rebuild = True
			args.remove( arg )

	printDependents = False
	printDependentsDepth = 0
	for arg in PRINT_DEPENDENTS:
		if arg in args:
			idx = args.index( arg )
			if args[ idx+1 ].isdigit():
				printDependentsDepth = int( args[ idx+1 ] )
				if printDependentsDepth < 1:
					printDependentsDepth = 0

				args.pop( idx+1 )

			printDependents = True
			args.remove( arg )

	printDependencies = False
	printDependenciesDepth = 1
	for arg in PRINT_DEPENDENCIES:
		if arg in args:
			idx = args.index( arg )
			if args[ idx+1 ].isdigit():
				printDependenciesDepth = int( args[ idx+1 ] )
				if printDependenciesDepth < 1:
					printDependenciesDepth = None

				args.pop( idx+1 )

			printDependencies = True
			args.remove( arg )

	printTree = False
	printTreeDepth = None
	for arg in PRINT_TREE_ARGS:
		if arg in args:
			idx = args.index( arg )
			if args[ idx+1 ].isdigit():
				printTreeDepth = int( args[ idx+1 ] )
				if printTreeDepth < 1:
					printTreeDepth = None

				args.pop( idx+1 )

			printTree = True
			args.remove( arg )

	printTests = False
	for arg in PRINT_TESTS_ARGS:
		if arg in args:
			printTests = True
			args.remove( arg )

	package = False
	for arg in PACKAGE_SCRIPTS:
		if arg in args:
			package = True
			args.remove( arg )

	files = []
	for f in args:
		if not os.path.isabs( f ):
			f = os.path.abspath( f )

		if not os.path.exists( f ):
			print >> Warn, 'FYI: %s cannot be found on disk.  Dependency query can still be performed, but you should know' % f

		files.append( f )

	depTree = None
	if not files:
		if updateCache:
			depTree = dependencies.generateDepTree( rebuildCache=rebuild )

		return

	if depTree is None:
		depTree = dependencies.generateDepTree( rebuildCache=rebuild )

	for n, f in enumerate( files ):
		if printTree:
			logHighlight( '-- DEPENDENCY TREE (DEPTH %s) FOR %s' % (printTreeDepth if printTreeDepth else 'deep', f) )
			dependencies.printDepTree( f, depTree, printTreeDepth )
			print

		if printDependents:
			pf, sf = depTree.findDependents( f )
			deps = pf

			logHighlight( '-- %d DEPENDENTS THAT IMMEDIATELY IMPORT %s' % (len( deps ), f) )
			for ff in sorted( deps ):
				print ff

			if printDependentsDepth > 0:
				deps = sf.difference( pf )
				logHighlight( '-- %d ADDITIONAL DEPENDENTS THAT INDIRECTLY IMPORT %s' % (len( deps ), f) )
				for ff in sorted( deps ):
					print ff

			print

		if printDependencies:
			deps = depTree.findDependencies( f, printDependenciesDepth, False )
			if deps:
				logHighlight( '-- %d IMPORT DEPENDENCIES FOR %s' % (len( deps ), f) )
				for ff in deps:
					print ff
			else:
				logHighlight( '-- NO IMPORT DEPENDENCIES FOR %s' % f )

			print

		if printTests:
			tests = dependencies.getScriptTests( f, depTree )
			if not tests:
				logHighlight( '-- THERE ARE NO TESTS FOR %s' % f )
			else:
				logHighlight( '-- THE FOLLOWING TESTS PROBABLY EXERCISE %s' % f )
				for ff in tests:
					print ff

			print

		setConsoleColour( BRIGHT | FG_YELLOW )
		pf, sf = depTree.findDependents( f )
		setConsoleColour( FG_WHITE )

		if n:
			logHighlight( '---------------------' )
			print

	if package:
		packageFilepath = dependencies.packageScripts( files[:], files[0], depTree )
		if packageFilepath is None:
			logWarning( '-- NO IMPORT DEPENDENCIES - no package file was written' )
		else:
			logHighlight( '-- PACKAGE WRITTEN TO %s' % packageFilepath )


try:
	main()
except KeyboardInterrupt:
	logWarning( "Aborted by user" )
	sys.exit( 0 )


#end
