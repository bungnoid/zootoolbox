
import sys
import baseSkeletonBuilder

from zooPy.path import Path
from baseSkeletonBuilder import *

__author__ = 'hamish@macaronikazoo.com'

SKELETON_PART_SCRIPT_PREFIX = 'skeletonPart_'

_LOAD_ORDER = 'spine', 'head', 'arm', 'hand', 'leg'


def _iterSkeletonPartScripts():
	for p in sys.path:
		p = Path( p )
		if 'maya' in p:
			for f in p.files():
				if f.hasExtension( 'py' ):
					if f.name().startswith( SKELETON_PART_SCRIPT_PREFIX ):
						yield f

partModuleNames = [ f.name() for f in _iterSkeletonPartScripts() ]
for name in reversed( _LOAD_ORDER ):
	name = SKELETON_PART_SCRIPT_PREFIX + name
	if name in partModuleNames:
		partModuleNames.remove( name )
		partModuleNames.insert( 0, name )

for modName in partModuleNames:
	__import__( modName )


#import skeletonBuilderConversion
#skeletonBuilderConversion.convertOldParts()


#end
