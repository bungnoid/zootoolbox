
import apiExtensions

from maya.cmds import *
from filesystem import removeDupes


def resetAttrs( obj, skipVisibility=True ):
	'''
	simply resets all keyable attributes on a given object to its default value
	great for running on a large selection such as all character controls...
	'''

	#obj = apiExtensions.asMObject( obj )
	attrs = listAttr( obj, k=True, s=True, m=True ) or []
	if skipVisibility:
		if 'visibility' in attrs:
			attrs.remove( 'visibility' )

	#if the transform is a joint, see if its part of a bindpose, and if so, restore to
	#the bindpose, not zero, as this is generally the preferred behaviour
	poses = listConnections( obj, s=False, type='dagPose' )
	bindPoses = []

	if poses:
		poses = removeDupes( poses )
		for pose in poses:
			if getAttr( '%s.bindPose' % pose ):
				bindPoses.append( pose )

	numBindPoses = len( bindPoses )

	if numBindPoses == 1:
		dagPose( obj, r=True, bp=True )

	#in this case we want to throw a list of bindposes to the user and let them pick which bindpose to go to
	elif numBindPoses > 1:
		dagPose( obj, r=True, name=bindPoses[ 0 ] )

	#otherwise just reset attribute values
	else:
		if not attrs:
			return

		selAttrs = channelBox( 'mainChannelBox', q=True, sma=True ) or channelBox( 'mainChannelBox', q=True, sha=True )

		for attr in attrs:

			#if there are selected attributes AND the current attribute isn't in the list of selected attributes, skip it...
			if selAttrs:
				attrShortName = attributeQuery( attr, n=obj, shortName=True )
				if attrShortName not in selAttrs:
					continue

			default = 0

			try:
				default = attributeQuery( attr, n=obj, listDefault=True )[ 0 ]
			except RuntimeError: pass

			attrpath = '%s.%s' % (obj, attr)
			if not getAttr( attrpath, settable=True ):
				continue

			#need to catch because maya will let the default value lie outside an attribute's
			#valid range (ie maya will let you creat an attrib with a default of 0, min 5, max 10)
			try:
				setAttr( attrpath, default )
			except RuntimeError: pass


#end
