
from triggered import Trigger
from pymel.core import *
from names import camelCaseToNice
from filesystem import removeDupes

import re
import pymel.core as pymelCore
import triggered
import control
import utils

attrState = control.attrState
AXES = utils.Axis.BASE_AXES


def build( src, tgts, names=None, space=None, **kw ):
	'''
	'''
	if names is None:
		names = [ None for t in tgts ]

	conditions = []
	for tgt, name in zip( tgts, names ):
		cond = add( src, tgt, name, space, **kw )
		conditions.append( cond )

	return conditions


CONSTRAINT_TYPES = CONSTRAINT_PARENT, CONSTRAINT_POINT, CONSTRAINT_ORIENT = 'parentConstraint', 'pointConstraint', 'orientConstraint'

NO_TRANSLATION = { 'skipTranslationAxes': ('x', 'y', 'z') }
NO_ROTATION = { 'skipRotationAxes': ('x', 'y', 'z') }

def add( src, tgt,
         name=None,
         space=None,
         maintainOffset=True,
         nodeWithParentAttr=None,
         skipTranslationAxes=(),
         skipRotationAxes=(),
         constraintType=CONSTRAINT_PARENT ):

	#make sure everything passed in is a PyNode - this may be being called from a script that doesn't yet use pymel...
	if not isinstance( src, PyNode ): src = PyNode( src )
	if not isinstance( tgt, PyNode ): tgt = PyNode( tgt )

	global AXES
	AXES = list( AXES )

	if space is None:
		space = src.getParent()

	if nodeWithParentAttr is None:
		nodeWithParentAttr = src

	if not name:
		name = camelCaseToNice( str( tgt ) )


	#if there is an existing constraint, check to see if the target already exists in its target list - if it does, return the condition used it uses
	attrState( space, ('t', 'r'), lock=False )
	existingConstraint = listConnections( space, type='constraint', d=False )
	if existingConstraint:
		existingConstraint = removeDupes( existingConstraint )
		assert len( existingConstraint ) == 1, "More than one constraint found? WTF FAIL!"

		existingConstraint = existingConstraint[ 0 ]

		constraintFunc = existingConstraint.__melcmd__
		targetsOnConstraint = constraintFunc( existingConstraint, q=True, tl=True )
		if tgt in targetsOnConstraint:
			idx = targetsOnConstraint.index( tgt )
			aliases = constraintFunc( existingConstraint, q=True, weightAliasList=True )
			cons = listConnections( existingConstraint.attr( aliases[ idx ] ), type='condition', d=False )
			return cons[ 0 ]


	#when skip axes are specified maya doesn't handle things properly - so make sure
	#ALL transform channels are connected, and remove unwanted channels at the end...
	preT, preR = space.t.get(), space.r.get()
	if existingConstraint:
		for channel, constraintAttr in zip( ['t', 'r'], ['ct', 'cr'] ):
			for axis in AXES:
				spaceAttr = space.attr( channel + axis )
				conAttr = existingConstraint.attr( constraintAttr + axis )
				if not isConnected( conAttr, spaceAttr ):
					connectAttr( conAttr, spaceAttr )


	#get the names for the parents from the parent enum attribute
	cmdOptionKw = { 'mo': True } if maintainOffset else {}
	if nodeWithParentAttr.hasAttr( "parent" ):
		srcs, names = getSpaceTargetsNames( src )
		nodeWithParentAttr.parent.setEnums( names + [name] )

		#if we're building a pointConstraint instead of a parent constraint AND we already
		#have spaces on the object, we need to turn the -mo flag off regardless of what the
		#user set it to, as the pointConstraint maintain offset has different behaviour to
		#the parent constraint
		if constraintType in ( CONSTRAINT_POINT, CONSTRAINT_ORIENT ):
			cmdOptionKw = {}
	else:
		nodeWithParentAttr.addAttr( 'parent', at="enum", en=name )
		nodeWithParentAttr.parent.setKeyable( True )


	#now build the constraint
	constraintFunction = globals()[ constraintType ]
	constraint = constraintFunction( tgt, space, **cmdOptionKw )


	weightAliasList = constraintFunction( constraint, q=True, weightAliasList=True )
	targetCount = len( weightAliasList )
	constraintAttr = weightAliasList[ -1 ]
	condition = shadingNode( 'condition', asUtility=True, n='%s_to_space_%s#' % (src.shortName(), tgt.shortName()) )

	condition.secondTerm.set( targetCount-1 )
	condition.colorIfTrue.set( (1, 1, 1) )
	condition.colorIfFalse.set( (0, 0, 0) )
	connectAttr( nodeWithParentAttr.parent, condition.firstTerm )
	connectAttr( condition.outColorR, constraintAttr )


	#find out what symbol to use to find the parent attribute
	parentAttrIdx = 0
	if space != src:
		parentAttrIdx = triggered.addConnect( src, nodeWithParentAttr )


	#add the zooObjMenu commands to the object for easy space switching
	Trigger.CreateMenu( src,
	                    "parent to %s" % name,
	                    "zooFlags;\nzooUtils;\nzooChangeSpace \"-attr parent %d\" %%%d;" % (targetCount-1, parentAttrIdx) )


	#when skip axes are specified maya doesn't handle things properly - so make sure
	#ALL transform channels are connected, and remove unwanted channels at the end...
	for axis, value in zip( AXES, preT ):
		if axis in skipTranslationAxes:
			attr = space.attr( 't'+ axis )
			delete( attr, icn=True )
			attr.set( value )

	for axis, value in zip( AXES, preR ):
		if axis in skipRotationAxes:
			attr = space.attr( 'r'+ axis )
			delete( attr, icn=True )
			attr.set( value )


	#make the space node non-keyable and lock visibility
	attrState( space, [ 't', 'r', 's' ], lock=True )
	attrState( space, 'v', *control.HIDE )


	return condition


def removeSpace( src, tgt ):
	'''
	removes a target (or space) from a "space switching" object
	'''
	tgts = []
	names = []
	name = ""
	delete = False

	tgts, names = getSpaceTargetsNames( src )
	for aTgt, aName in zip( tgts, names ):
				if aTgt == tgt:
					name = aName
					break

	if not name:
		raise AttributeError( "no such target" )

	if len( tgts ) == 1:
		delete = True

	constraint = findConstraint( src )

	parentAttrOn = findSpaceAttrNode( src )
	space = findSpace( src )

	srcTrigger = Trigger( src )
	cmds = srcTrigger.iterMenus()

	if delete:
		delete( constraint )
		deleteAttr( src.parent )
	else:
		constraintType = nodeType( constraint )
		constraintFunc = globals()[ constraintType ]
		constraintFunc( constraint, rm=tgt )

	for slot, cmdName, cmdStr in srcTrigger.iterMenus():
		if cmdName == ( "parent to %s" % name ):
			srcTrigger.removeMenu( slot )

		#rebuild the parent attribute
		idx = tgts.index( tgt )
		tgts, names = getSpaceTargetsNames( src )
		if names:
			addAttr( parentAttrOn.parent, e=True, enumName=':'.join( names ) )

	#now we need to update the indicies in the right click command
	for slot, cmdName, cmdStr in srcTrigger.iterMenus():
		if cmdName != ( "parent to %s" % name ): continue

		cmdLines = cmdStr.split( '\n' )
		lineToks = cmdLines[ 2 ].split( ' ' )

		parentIdx = re.search( '^[0-9]+', lineToks[ 3 ] )
		lineToks[ 3 ] = re.sub( '^[0-9]+', str( parentIdx-1 ), lineToks[ 3 ] )
		cmdLines[ 2 ] = '%s;' % ' '.join( lineToks )

		newCmdStr = '\n'.join( cmdLines )
		srcTrigger.setMenuCmd( slot, newCmdStr )

		#if !`size $names` ) zooAttrState "-attrs t r -k 1 -l 0" $space;


def getSpaceName( src, theTgt ):
	'''
	will return the user specified name given to a particular target object
	'''
	tgts, names = getSpaceTargetsNames( src )
	for tgt, name in zip( tgts, names ):
		if tgt == theTgt:
			return name


def getSpaceTargetsNames( src ):
	'''
	this procedure returns a 2-tuple: a list of all targets, and a list of user
	specified names - for the right click menus
	'''
	constraint = findConstraint( src )
	if constraint is None:
		return [], []

	space = findSpace( src )
	if space is None:
		return [], []

	constraintType = nodeType( constraint )
	constraintFunc = globals()[ constraintType ]

	targetsOnConstraint = constraintFunc( constraint, q=True, tl=True )
	trigger = Trigger( src )

	SPECIAL_STRING = 'parent to '
	LEN_SPECIAL_STRING = len( SPECIAL_STRING )

	digitsRE = re.compile( '[0-9]+' )

	tgts, names = [], []
	for slotIdx, slotName, slotCmd in trigger.iterMenus():
		if slotName.startswith( SPECIAL_STRING ):
			names.append( slotName[ LEN_SPECIAL_STRING: ] )

			lines = slotCmd.split( '\n' )
			for line in lines:
				if line.startswith( 'zooChangeSpace ' ):
					lineToks = line.split( ' ' )

					index = digitsRE.search( lineToks[ -1 ] )
					index = int( index.group() )

					tgts.append( targetsOnConstraint[ index ] )

	return tgts, names


def findSpace( obj ):
	'''
	will return the node being used as the "space node" for any given space switching object
	'''
	constraint = findConstraint( obj )
	if constraint is None:
		return None

	spaces = constraint.ctx.listConnections( type='transform', s=False )
	if spaces:
		future = ls( listHistory( constraint.ctx, f=True ), type='transform' )
		if future:
			return future[ -1 ]


def findConstraint( obj ):
	'''
	will return the name of the constraint node thats controlling the "space node" for any given
	space switching object
	'''
	parentAttrOn = findSpaceAttrNode( obj )
	if parentAttrOn is None:
		return None

	conditions = parentAttrOn.parent.listConnections( type='condition', s=False )
	for condition in conditions:
		constraints = condition.outColorR.listConnections( type='constraint', s=False )
		if constraints:
			return constraints[ 0 ]

	return None


#pymel.ls( sl=1 )[0 ].parent.getEnums()
def findSpaceAttrNode( obj ):
	'''
	returns the PyNode that contains the parent attribute for the space switch
	'''
	parentAttrOn = "";
	trigger = Trigger( obj )

	for slotIdx, slotName, slotCmd in trigger.iterMenus():
		if slotName.startswith( 'parent to ' ):
			lines = slotCmd.split( '\n' )
			for line in lines:
				if line.startswith( 'zooChangeSpace ' ):
					lastToken = line.split( ' ' )[ -1 ].replace( ';', '' )
					try:
						nodeWithParentAttr = PyNode( trigger.resolve( lastToken ) )
					except MayaNodeError: return None

					return nodeWithParentAttr


#end
