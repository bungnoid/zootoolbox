
from baseRigPrimitive import *
from apiExtensions import cmpNodes


ARM_NAMING_SCHEME = 'arm', 'bicep', 'elbow', 'wrist'
LEG_NAMING_SCHEME = 'leg', 'thigh', 'knee', 'ankle'

class IkFkBase(RigSubPart):
	'''
	this is a subpart, not generally exposed directly to the user
	'''
	__version__ = 2
	CONTROL_NAMES = 'control', 'fkUpper', 'fkMid', 'fkLower', 'poleControl', 'ikSpace', 'fkSpace', 'ikHandle', 'endOrient', 'poleTrigger'
	ADD_CONTROLS_TO_QSS = False

	def _build( self, skeletonPart, **kw ):
		return self.doBuild( *skeletonPart.getIkFkItems(), **kw )
	def doBuild( self, bicep, elbow, wrist, nameScheme=ARM_NAMING_SCHEME, alignEnd=False, **kw ):
		idx = kw[ 'idx' ]
		scale = kw[ 'scale' ]

		parity = Parity( idx )
		suffix = parity.asName()

		worldPart = WorldPart.Create()
		worldControl = worldPart.control
		partsControl = worldPart.parts

		colour = ColourDesc( 'green' ) if parity == Parity.LEFT else ColourDesc( 'red' )


		#grab a list of 'bicep joints' - these are the child joints of the bicep that aren't the elbow or any of its
		#children.  these joints are usually involved in deformation related to the bicep so we want to capture them
		#to use for geometry extraction for the control representation
		bicepJoints = [ bicep ]
		for child in listRelatives( bicep, pa=True, type='joint' ) or []:
			if cmpNodes( child, elbow ): continue
			bicepJoints.append( child )
			bicepJoints += listRelatives( child, type='joint', pa=True, ad=True ) or []

		#grab the 'elbow joints' as per the above description
		elbowJoints = [ elbow ]
		for child in listRelatives( elbow, pa=True, type='joint' ) or []:
			if cmpNodes( child, wrist ): continue
			elbowJoints.append( child )
			elbowJoints += listRelatives( child, type='joint', pa=True, ad=True ) or []


		### BUILD THE FK CONTROLS
		ikArmSpace = buildAlignedNull( wrist, "ik_%sSpace%s" % (nameScheme[ 0 ], suffix), parent=worldControl )
		fkArmSpace = buildAlignedNull( bicep, "fk_%sSpace%s" % (nameScheme[ 0 ], suffix) )

		BONE_AXIS = AIM_AXIS + 3 if parity else AIM_AXIS
		driverUpper = buildControl( "fk_%sControl%s" % (nameScheme[ 1 ], suffix), bicep, PivotModeDesc.MID, shapeDesc=ShapeDesc( 'sphere' ), colour=colour, asJoint=True, oriented=False, scale=scale, parent=fkArmSpace )
		driverMid = buildControl( "fk_%sControl%s" % (nameScheme[ 2 ], suffix), elbow, PivotModeDesc.MID, shapeDesc=ShapeDesc( 'sphere' ), colour=colour, asJoint=True, oriented=False, scale=scale, parent=driverUpper )
		driverLower = buildControl( "fk_%sControl%s" % (nameScheme[ 3 ], suffix), PlaceDesc( wrist, wrist if alignEnd else None ), shapeDesc=ShapeDesc( 'sphere' ), colour=colour, asJoint=True, oriented=False, constrain=False, scale=scale )


		#don't parent the driverLower in the buildControl command otherwise the control won't be in worldspace
		parent( driverLower, driverMid )
		makeIdentity( driverLower )


		### BUILD THE POLE CONTROL
		polePos = rigUtils.findPolePosition( driverLower, driverMid, driverUpper, 5 )
		poleControl = buildControl( "%s_poleControl%s" % (nameScheme[ 0 ], suffix), PlaceDesc( elbow, PlaceDesc.WORLD ), shapeDesc=ShapeDesc( 'sphere', None ), colour=colour, constrain=False, parent=worldControl, scale=scale*0.5 )
		poleControlSpace = getNodeParent( poleControl )
		attrState( poleControlSpace, 'v', lock=False, show=True )

		move( polePos[0], polePos[1], polePos[2], poleControlSpace, a=True, ws=True, rpr=True )
		move( polePos[0], polePos[1], polePos[2], poleControl, a=True, ws=True, rpr=True )
		makeIdentity( poleControlSpace, a=True, t=True )
		setAttr( '%s.v' % poleControl, True )


		### BUILD THE POLE SELECTION TRIGGER
		lineNode = buildControl( "%s_poleSelectionTrigger%s" % (nameScheme[ 0 ], suffix), shapeDesc=ShapeDesc( 'sphere', None ), colour=ColourDesc( 'darkblue' ), scale=scale, constrain=False, oriented=False, parent=ikArmSpace )
		lineStart, lineEnd, lineShape = buildAnnotation( lineNode )

		parent( lineStart, poleControl )
		delete( pointConstraint( poleControl, lineStart ) )
		pointConstraint( elbow, lineNode )
		attrState( lineNode, ('t', 'r'), *LOCK_HIDE )

		setAttr( '%s.template' % lineStart, 1 )  #make the actual line unselectable


		#build the IK handle
		ikHandle = cmd.ikHandle( fs=1, sj=driverUpper, ee=driverLower, solver='ikRPsolver', n=( '%sIkHandle%s' % ( nameScheme[0], parity.asName() ) ) )[ 0 ]
		limbControl = buildControl( '%sControl%s' % (nameScheme[ 0 ], suffix), PlaceDesc( wrist, wrist if alignEnd else None ), shapeDesc=ShapeDesc( 'cube' ), colour=colour, scale=scale, constrain=False, parent=ikArmSpace )

		xform( limbControl, p=True, rotateOrder='yzx' )
		setAttr( '%s.snapEnable' % ikHandle, False )
		setAttr( '%s.v' % ikHandle, False )

		addAttr( limbControl, ln='ikBlend', shortName='ikb', dv=1, min=0, max=1, at='double' )
		setAttr( '%s.ikBlend' % limbControl, keyable=True )
		connectAttr( '%s.ikBlend' % limbControl, '%s.ikBlend' % ikHandle )

		attrState( ikHandle, 'v', *LOCK_HIDE )
		parent( ikHandle, partsControl )
		parentConstraint( limbControl, ikHandle )

		poleVectorConstraint( poleControl, ikHandle )


		#setup constraints to the wrist - it is handled differently because it needs to blend between the ik and fk chains (the other controls are handled by maya)
		wristOrientParent = buildAlignedNull( wrist, "%s_follow%s_space" % (nameScheme[ 3 ], suffix), parent=partsControl )
		wristOrient = buildAlignedNull( wrist, "%s_follow%s" % (nameScheme[ 3 ], suffix), parent=wristOrientParent )

		pointConstraint( driverLower, wrist )
		orientConstraint( wristOrient, wrist, mo=True )
		setItemRigControl( wrist, wristOrient )
		setNiceName( wristOrient, 'Fk %s' % nameScheme[3]  )
		wristSpaceOrient = parentConstraint( limbControl, wristOrientParent, weight=0, mo=True )[ 0 ]
		wristSpaceOrient = parentConstraint( driverLower, wristOrientParent, weight=0, mo=True )[ 0 ]

		#constraints to drive the "wrist follow" mode
		wristFollowConstraint = parentConstraint( wristOrientParent, wristOrient )[0]
		wristFollowConstraint = parentConstraint( driverLower, wristOrient, mo=True )[0]


		#
		wristFollowAttrs = listAttr( wristFollowConstraint, ud=True )
		addAttr( limbControl, ln='orientToIk', at='double', min=0, max=1, dv=1 )
		attrState( limbControl, 'orientToIk', keyable=True, show=True )
		expression( s='%s.%s = %s.orientToIk;\n%s.%s = 1 - %s.orientToIk;' % (wristFollowConstraint, wristFollowAttrs[0], limbControl, wristFollowConstraint, wristFollowAttrs[1], limbControl), n='wristFollowConstraint_on_off' )


		#connect the ikBlend of the arm controller to the orient constraint of the fk wrist - ie turn it off when ik is off...
		weightRevNode = shadingNode( 'reverse', asUtility=True )
		wristOrientAttrs = listAttr( wristSpaceOrient, ud=True )
		connectAttr( '%s.ikBlend' % limbControl, '%s.inputX' % weightRevNode, f=True )
		connectAttr( '%s.ikBlend' % limbControl, '%s.%s' % (wristSpaceOrient, wristOrientAttrs[ 0 ]), f=True )
		connectAttr( '%s.outputX' % weightRevNode, '%s.%s' % (wristSpaceOrient, wristOrientAttrs[ 1 ]), f=True )


		#build expressions for fk blending and control visibility
		fkVisCond = shadingNode( 'condition', asUtility=True )
		poleVisCond = shadingNode( 'condition', asUtility=True )
		connectAttr( '%s.ikBlend' % limbControl, '%s.firstTerm' % fkVisCond, f=True )
		connectAttr( '%s.ikBlend' % limbControl, '%s.firstTerm' % poleVisCond, f=True )
		connectAttr( '%s.outColorG' % poleVisCond, '%s.v' % lineNode, f=True )
		connectAttr( '%s.outColorG' % poleVisCond, '%s.v' % poleControlSpace, f=True )
		connectAttr( '%s.outColorG' % poleVisCond, '%s.v' % limbControl, f=True )
		setAttr( '%s.secondTerm' % fkVisCond, 1 )

		expression( s='if ( %(limbControl)s.ikBlend > 0 && %(limbControl)s.orientToIk < 1 ) %(driverLower)s.visibility = 1;\nelse %(driverLower)s.visibility = %(fkVisCond)s.outColorG;' % locals(), n='wrist_visSwitch' )
		for driver in (driverUpper, driverMid):
			for shape in listRelatives( driver, s=True, pa=True ):
				connectAttr( '%s.outColorR' % fkVisCond, '%s.v' % shape, f=True )


		#add set pole to fk pos command to pole control
		fkControls = driverUpper, driverMid, driverLower
		poleTrigger = Trigger( poleControl )
		poleConnectNums = [ poleTrigger.connect( c ) for c in fkControls ]

		idx_toFK = poleTrigger.setMenuInfo( None,
			                                "move to FK position",
			                                'zooVectors;\nfloat $pos[] = `zooFindPolePosition "-start %%%s -mid %%%s -end %%%s"`;\nmove -rpr $pos[0] $pos[1] $pos[2] #;' % tuple( poleConnectNums ) )
		poleTrigger.setMenuInfo( None,
			                     "move to FK pos for all keys",
			                     'source zooKeyCommandsWin;\nzooSetKeyCommandsWindowCmd "eval(zooPopulateCmdStr(\\\"#\\\",(zooGetObjMenuCmdStr(\\\"#\\\",%%%d)),{}))";' % idx_toFK )


		#add IK/FK switching commands
		limbTrigger = Trigger( limbControl )
		handleNum = limbTrigger.connect( ikHandle )
		poleNum = limbTrigger.connect( poleControl )
		lowerNum = limbTrigger.connect( driverLower )
		fkIdx = limbTrigger.createMenu( "switch to FK",
			                            "zooAlign \"\";\nzooAlignFK \"-ikHandle %%%d -offCmd setAttr #.ikBlend 0\";\nselect %%%d;" % (handleNum, lowerNum) )
		limbTrigger.createMenu( "switch to FK for all keys",
			                    'source zooKeyCommandsWin;\nzooSetKeyCommandsWindowCmd "eval(zooPopulateCmdStr(\\\"#\\\",(zooGetObjMenuCmdStr(\\\"#\\\",%%%d)),{}))";' % fkIdx )
		ikIdx = limbTrigger.createMenu( "switch to IK",
			                            'zooAlign "";\nzooAlignIK "-ikHandle %%%d -pole %%%d -offCmd setAttr #.ikBlend 1;";' % (handleNum, poleNum) )
		limbTrigger.createMenu( "switch to IK for all keys",
			                    'source zooKeyCommandsWin;\nzooSetKeyCommandsWindowCmd "eval(zooPopulateCmdStr(\\\"#\\\",(zooGetObjMenuCmdStr(\\\"#\\\",%%%d)),{}))";' % ikIdx )


		#add all zooObjMenu commands to the fk controls
		for fk in fkControls:
			fkTrigger = Trigger( fk )
			c1 = fkTrigger.connect( ikHandle )
			c2 = fkTrigger.connect( poleControl )

			fkTrigger.createMenu( 'switch to IK',
				                  'zooAlign "";\nstring $cs[] = `listConnections %%%d.ikBlend`;\nzooAlignIK ("-ikHandle %%%d -pole %%%d -control "+ $cs[0] +" -offCmd setAttr "+ $cs[0] +".ikBlend 1;" );' % (c1, c1, c2) )

		createLineOfActionMenu( [limbControl] + list( fkControls ), (elbow, wrist) )


		#add trigger commands
		Trigger.CreateTrigger( lineNode, Trigger.PRESET_SELECT_CONNECTED, [ poleControl ] )
		setAttr( '%s.displayHandle' % lineNode, True )


		#turn unwanted transforms off, so that they are locked, and no longer keyable
		attrState( fkControls, ('t', 'radi'), *LOCK_HIDE )
		attrState( poleControl, 'r', *LOCK_HIDE )


		return limbControl, driverUpper, driverMid, driverLower, poleControl, ikArmSpace, fkArmSpace, ikHandle, wristOrient, lineNode


#end
