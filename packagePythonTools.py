
import os

from consoleChroma import Good
from filesystem import Path, removeDupes
from dependencies import generateDepTree, makeScriptPathRelative

_PACKAGE_DIR_NAME = 'zooToolboxPy'
_PACKAGE_DIR = Path( __file__ ).up( 2 ) / _PACKAGE_DIR_NAME

#this is the list of modules to package - these tools and all dependencies get packaged into the _PACKAGE_DIR
_MODULES_TO_PACKAGE = ( 'animLibUI', 'picker', 'poseSymUI',
                        'skeletonBuilderUI', 'skinWeightsUI',
                        'spaceSwitchingUI', 'visManagerUI',
                        'xferAnimUI' )


def cleanPackageDir():
	if _PACKAGE_DIR.exists:
		_PACKAGE_DIR.delete()

	_PACKAGE_DIR.create()


def buildPackage( dependencyTree=None ):
	cleanPackageDir()

	if dependencyTree is None:
		dependencyTree = generateDepTree()

	filesToPackage = []
	for moduleName in _MODULES_TO_PACKAGE:
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
