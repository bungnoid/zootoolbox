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

	__NAME_MAPPING_IS_BROKEN = True
	if __NAME_MAPPING_IS_BROKEN:
		'''
		its broken because it strips the namespace off before doing the matches - so it can erroneously
		think "ns:root" is an exact match to "root" if it comes before the item "root" in the tgtList
		'''
		srcs = []
		for i in mapping.srcs:
			if not cmd.objExists( i ):
				possibles = cmd.ls( '*%s' % i, r=True )
				if possibles: i = possibles[0]

			srcs.append( i )

		tgts = []
		for i in mapping.tgts:
			if not cmd.objExists( i ):
				possibles = cmd.ls( '*%s' % i, r=True )
				if possibles: i = possibles[0]

			tgts.append( i )
	else:
		srcs = matchNames( mapping.srcs, allItems, threshold=threshold )
		tgts = matchNames( mapping.tgts, allItems, threshold=threshold )

	return Mapping( srcs, tgts )


#end
