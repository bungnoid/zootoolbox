
from names import *
from apiExtensions import *


def findItem( itemName ):
	itemName = str( itemName )
	if cmd.objExists( itemName ):
		return itemName

	match = matchNames( itemName, cmd.ls( type='transform' ) )[ 0 ]
	if match:
		return match

	return None


def resolveMappingToScene( mapping, threshold=1.0 ):
	'''
	takes a mapping and returns a mapping with actual scene objects
	'''
	assert isinstance( mapping, Mapping )

	toSearch = cmd.ls( typ='transform' )
	existingSrcs = []
	existingTgts = []

	for src, tgt in mapping.iteritems():
		if not cmd.objExists( src ):
			src = matchNames( [ src ], toSearch, **kw )[ 0 ]

		if not cmd.objExists( tgt ):
			tgt = matchNames( [ tgt ], toSearch, **kw )[ 0 ]

		if cmd.objExists( src ) and cmd.objExists( tgt ):
			existingSrcs.append( src )
			existingTgts.append( tgt )

	return Mapping( existingSrcs, existingTgts )


#end
