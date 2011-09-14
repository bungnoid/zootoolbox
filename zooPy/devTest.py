
try:
	import wingdbstub
except ImportError: pass

import sys
import inspect

from unittest import TestCase, TestResult

from maya import cmds as cmd

from path import Path


### POPULATE THE LIST OF TEST SCRIPTS ###
TEST_SCRIPTS = {}

def populateTestScripts():
	global TEST_SCRIPTS

	thisScriptDir = Path( __file__ ).up()
	pathsToSearch = sys.path[:] + [ thisScriptDir ]
	for pyPath in pathsToSearch:
		pyPath = Path( pyPath )
		if pyPath.isDir():
			for f in pyPath.files():
				if f.hasExtension( 'py' ):
					if f.name().startswith( 'devTest_' ):
						TEST_SCRIPTS[ f ] = []

populateTestScripts()


### POPULATE TEST_CASES ###
TEST_CASES = []

def populateTestCases():
	global TEST_CASES

	for script in TEST_SCRIPTS:
		testModule = __import__( script.name() )

		scriptTestCases = TEST_SCRIPTS[ script ] = []
		for name, obj in testModule.__dict__.iteritems():
			if obj is TestCase:
				continue

			if isinstance( obj, type ):
				if issubclass( obj, TestCase ):
					if obj.__name__.startswith( '_' ):
						continue

					TEST_CASES.append( obj )
					scriptTestCases.append( obj )

populateTestCases()


def runTestCases( testCases=TEST_CASES ):
	thisPath = Path( __file__ ).up()
	testResults = TestResult()

	reloadedTestCases = []

	for test in testCases:
		#find the module the test comes from
		module = inspect.getmodule( test )

		performReload = getattr( module, 'PERFORM_RELOAD', True )

		#reload the module the test comes from
		if performReload:
			module = reload( module )

		#find the test object inside the newly re-loaded module and append it to the reloaded tests list
		reloadedTestCases.append( getattr( module, test.__name__ ) )

	for ATestCase in reloadedTestCases:
		testCase = ATestCase()
		testCase.run( testResults )

	#force a new scene
	cmd.file( new=True, f=True )

	OK = 'Ok'
	BUTTONS = (OK,)
	if testResults.errors:
		print '------------- THE FOLLOWING ERRORS OCCURRED -------------'
		for error in testResults.errors:
			print error[0]
			print error[1]
			print '--------------------------'

		cmd.confirmDialog( t='TEST ERRORS OCCURRED!', m='Errors occurred running the tests - see the script editor for details!', b=BUTTONS, db=OK )
	else:
		print '------------- %d TESTS WERE RUN SUCCESSFULLY -------------' % len( testCases )
		cmd.confirmDialog( t='SUCCESS!', m='All tests were successful!', b=BUTTONS, db=OK )

	return testResults


#end
