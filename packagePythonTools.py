
import os

from consoleChroma import Good
from filesystem import Path, removeDupes
from dependencies import generateDepTree, makeScriptPathRelative

_THIS_FILE = Path( os.path.abspath( __file__ ) )
_PYTHON_TOOLS_TO_PACKAGE = _THIS_FILE.up() / 'pythonToolsToPackage.txt'
_PACKAGE_DIR_NAME = 'zooToolboxPy'
_PACKAGE_DIR = _THIS_FILE.up( 2 ) / _PACKAGE_DIR_NAME


def cleanPackageDir():
	if _PACKAGE_DIR.exists:
		_PACKAGE_DIR.delete()

	_PACKAGE_DIR.create()


def buildPackage( dependencyTree=None ):
	if not _PYTHON_TOOLS_TO_PACKAGE.exists:
		raise ValueError( "Cannot find %s file!" % _PYTHON_TOOLS_TO_PACKAGE.name() )

	modulesToPackage = []
	for toolName in _PYTHON_TOOLS_TO_PACKAGE.read():
		if toolName:
			if toolName.startswith( '#' ):
				continue
			elif toolName.startswith( '//' ):
				continue

			modulesToPackage.append( toolName )

	cleanPackageDir()

	if dependencyTree is None:
		dependencyTree = generateDepTree()

	filesToPackage = []
	for moduleName in modulesToPackage:
		moduleScriptPath = dependencyTree.moduleNameToScript( moduleName )
		filesToPackage += dependencyTree.findDependencies( moduleScriptPath, None, False )

	if not filesToPackage:
		return None

	#remove any duplicate files...
	filesToPackage = removeDupes( filesToPackage )

	#this is a little hacky - but we don't want to re-distribute wingdbstub so lets check to see if its in the list of files
	for f in filesToPackage:
		if f.name() == 'wingdbstub':
			filesToPackage.remove( f )
			break

	print >> Good, "Found dependencies - %d files" % len( filesToPackage )
	for f in filesToPackage:
		relativePath = makeScriptPathRelative( f )
		packagedPath = _PACKAGE_DIR / relativePath
		if len( relativePath ) > 1:
			packagedPath.up().create()

		f.copy( packagedPath )
		print 'copying ---->   %s' % f

	#now zip up the files into a package
	cmdStr = '7z a -r ..\\%s\\zooToolBoxPy.7z ..\\%s\\' % (_PACKAGE_DIR_NAME, _PACKAGE_DIR_NAME)
	os.system( cmdStr )

	#now write a simple mel script to load the toolbox UI
	cmdStr = """global proc zooToolBox() { return; }"""
	bootstrapMelScript = _PACKAGE_DIR / 'zooToolBox.mel'
	bootstrapMelScript.write( cmdStr )


if __name__ == '__main__':
	buildPackage()


#end
