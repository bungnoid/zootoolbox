from rigPrim_base import *


class Hand(RigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( skeletonBuilderCore.Hand, )
	CONTROL_NAMES = 'control', 'poses', 'qss'

	ADD_CONTROLS_TO_QSS = False

	@classmethod
	def _build( cls, skeletonPart, taper=0.8, **kw ):
		worldPart = WorldPart.Create()
		qss = worldPart.qss

		controls = hand( skeletonPart.bases, taper=taper, **kw )
		for c, n in zip( controls, cls.CONTROL_NAMES ):
			qss.add( c )

		return controls


FINGER_IDX_NAMES = vSkeletonBuilder.FINGER_IDX_NAMES

def hand( bases, wrist=None, num=0, names=FINGER_IDX_NAMES, taper=0.8, **kw ):
	if wrist is None:
		wrist = bases[ 0 ].getParent()

	scale = kw[ 'scale' ]

	idx = kw[ 'idx' ]
	parity = Parity( idx )
	colour = ColourDesc( 'orange' )

	suffix = parity.asName()
	parityMult = parity.asMultiplier()

	worldPart = WorldPart.Create()
	partsControl = worldPart.parts
	partParent, rootControl = getParentAndRootControl( bases[ 0 ] )


	minSlider = -90
	maxSlider = 90
	minFingerRot = -45  #rotation at minimum slider value
	maxFingerRot = 90  #rotation at maxiumum slider value


	#get the bounds of the geo skinned to the hand and use it to determine default placement of the slider control
	bounds = utils.getJointBounds( [ wrist ] + bases )
	backwardAxis = utils.getObjectAxisInDirection( wrist, Vector( (0, 0, -1) ) )
	dist = bounds[ not backwardAxis.isNegative() ][ backwardAxis % 3 ]


	#build the main hand group, and the slider control for the fingers
	handSliders = buildControl( "hand_sliders"+ suffix, wrist, shapeDesc=ShapeDesc( None, 'pointer', backwardAxis ), constrain=False, colour=colour, offset=(0, 0, dist*1.25), scale=scale*1.25 )
	poseCurve = buildControl( "hand_poses"+ suffix, handSliders, shapeDesc=ShapeDesc( None, 'starCircle', AX_Y ), oriented=False, constrain=False, colour=colour, parent=handSliders, scale=scale )
	handQss = sets( empty=True, text="gCharacterSet", n="hand_ctrls"+ suffix )
	handGrp = handSliders.getParent()

	poseCurveTrigger = Trigger( poseCurve )
	poseCurve.v.set( False )

	#constrain the group to the wrist
	parentConstraint( wrist, handGrp )
	parent( handGrp, partsControl )

	attrState( (handSliders, poseCurve), ('t', 'r'), *LOCK_HIDE )

	poseCurve.addAttr( 'controlObject', at='message' )  #build the attribute so posesToSliders knows where to write the pose sliders to when poses are rebuilt
	connectAttr( handSliders.message, poseCurve.controlObject )


	#now start building the controls
	allCtrls = [ handSliders, poseCurve, handQss ]
	allSpaces = []
	allConstraints = []
	baseControls = []
	baseSpaces = []
	slider_curl = []
	slider_bend = []

	for n, base in enumerate( bases ):
		#discover the list of joints under the current base
		name = names[ n ]

		if not num: num = 100

		joints = [ base ]
		for i in range( num ):
			children = listRelatives( joints[ -1 ], type='joint' )
			if not children: break
			joints.append( children[ 0 ] )

		num = len( joints )

		#build the controls
		ctrls = []
		for i, j in enumerate( joints ):
			ctrlScale = scale * (taper ** i)

			c = buildControl( "%sControl_%d%s" % (name, i, suffix), j, shapeDesc=ShapeDesc( 'sphere', 'ring', axis=AIM_AXIS ), colour=colour, parent=handGrp, scale=ctrlScale, qss=handQss )
			c.v = False  #hidden by default
			cParent = c.getParent()
			if i:
				parent( cParent, ctrls[ -1 ] )

			ctrls.append( c )

			poseCurveTrigger.connect( c.getParent() )

		allCtrls += ctrls


		###------
		###CURL SLIDERS
		###------
		driverAttr = name +"Curl"

		handSliders.addAttr( driverAttr, k=True, at='double', min=minSlider, max=maxSlider, dv=0 )
		driverAttr = handSliders.attr( driverAttr )
		driverAttr.setKeyable( True )
		spaces = [ c.getParent() for c in ctrls ]
		for s in spaces:
			setDrivenKeyframe( s.r, cd=driverAttr )

		driverAttr.set( maxSlider )
		for s in spaces:
			rotate( s, ( 0, maxFingerRot * parityMult, 0), r=True, os=True )
			setDrivenKeyframe( s.r, cd=driverAttr )

		driverAttr.set( minSlider )
		for s in spaces:
			rotate( s, ( 0, minFingerRot * parityMult, 0), r=True, os=True )
			setDrivenKeyframe( s.r, cd=driverAttr )

		driverAttr.set( 0 )
		slider_curl.append( driverAttr.shortName() )


		###------
		###BEND SLIDERS
		###------
		driverAttr = name +"Bend"

		handSliders.addAttr( driverAttr, k=True, at='double', min=minSlider, max=maxSlider, dv=0 )
		driverAttr = handSliders.attr( driverAttr )
		driverAttr.setKeyable( True )

		baseCtrlSpace = spaces[ 0 ]
		setDrivenKeyframe( baseCtrlSpace.r, cd=driverAttr )

		driverAttr.set( maxSlider )
		rotate( baseCtrlSpace, ( 0, maxFingerRot * parityMult, 0), r=True, os=True )
		setDrivenKeyframe( baseCtrlSpace.r, cd=driverAttr )

		driverAttr.set( minSlider )
		rotate( baseCtrlSpace, ( 0, minFingerRot * parityMult, 0), r=True, os=True )
		setDrivenKeyframe( baseCtrlSpace.r, cd=driverAttr )

		driverAttr.set( 0 )
		slider_bend.append( driverAttr.shortName() )


	#reorder the finger sliders
	attrOrder = slider_curl + slider_bend
	mel.zooReorderAttrs( str( handSliders ), attrOrder )


	#add toggle finger control vis
	handSlidersTrigger = Trigger( handSliders )
	qssIdx = handSlidersTrigger.connect( handQss )
	handSlidersTrigger.createMenu( 'Toggle Finger Controls',
	                               'string $objs[] = `sets -q %%%d`;\nint $vis = !getAttr( $objs[0] +".v" );\nfor( $o in $objs ) setAttr( $o +".v", $vis );' % qssIdx )


	return allCtrls


#end
