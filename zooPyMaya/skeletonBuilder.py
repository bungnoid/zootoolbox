
import sys
import baseSkeletonBuilder

from zooPy.path import Path
from baseSkeletonBuilder import *

__author__ = 'hamish@macaronikazoo.com'

SKELETON_PART_SCRIPT_PREFIX = 'skeletonPart_'

_LOAD_ORDER = 'spine', 'head', 'arm', 'hand', 'leg'


def _iterSkeletonPartScripts():
	for f in Path( __file__ ).up().files():
		if f.hasExtension( 'py' ):
			if f.name().startswith( SKELETON_PART_SCRIPT_PREFIX ):
				yield f

def _importSkeletonPartScripts():
	for f in _iterSkeletonPartScripts():
		execfile( f )

_importSkeletonPartScripts()

#end
