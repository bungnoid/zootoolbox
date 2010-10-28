
from baseSkeletonBuilder import *


class QuadrupedFrontLeg(SkeletonPart.GetNamedSubclass( 'Arm' )):
	'''
	A quadruped's front leg is more like a biped's arm as it has clavicle/shoulder
	blade functionality, but is generally positioned more like a leg.  It is a separate
	part because it is rigged quite differently from either a bipedal arm or a bipedal
	leg.
	'''

	AVAILABLE_IN_UI = True

	@classmethod
	def _build( cls, parent=None, **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )
		height = xform( parent, q=True, ws=True, rp=True )[ 1 ]

		dirMult = idx.asMultiplier()
		parityName = idx.asName()

		clavicle = createJoint( 'quadClavicle%s' % parityName )
		cmd.parent( clavicle, parent, relative=True )
		move( dirMult * partScale / 10.0, -partScale / 10.0, partScale / 6.0, clavicle, r=True, ws=True )

		bicep = createJoint( 'quadHumerous%s' % parityName )
		cmd.parent( bicep, clavicle, relative=True )
		move( 0, -height / 3.0, -height / 6.0, bicep, r=True, ws=True )

		elbow = createJoint( 'quadElbow%s' % parityName )
		cmd.parent( elbow, bicep, relative=True )
		move( 0, -height / 3.0, height / 10.0, elbow, r=True, ws=True )

		wrist = createJoint( 'quadWrist%s' % parityName )
		cmd.parent( wrist, elbow, relative=True )
		move( 0, -height / 3.0, 0, wrist, r=True, ws=True )

		jointSize( clavicle, 2 )
		jointSize( wrist, 2 )

		return [ clavicle, bicep, elbow, wrist ]


class QuadrupedBackLeg(SkeletonPart.GetNamedSubclass( 'Arm' )):
	'''
	The creature's back leg is more like a biped's leg in terms of the joints it contains.
	However, like the front leg, the creature stands on his "tip toes" at the back as well.
	'''

	AVAILABLE_IN_UI = True

	@classmethod
	def _build( cls, parent=None, **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )
		height = xform( parent, q=True, ws=True, rp=True )[ 1 ]

		dirMult = idx.asMultiplier()
		parityName = idx.asName()

		kneeFwdMove = height / 10.0

		thigh = createJoint( 'quadThigh%s' % parityName )
		thigh = cmd.parent( thigh, parent, relative=True )[ 0 ]
		move( dirMult * partScale / 10.0, -partScale / 10.0, -partScale / 5.0, thigh, r=True, ws=True )

		knee = createJoint( 'quadKnee%s' % parityName )
		knee = cmd.parent( knee, thigh, relative=True )[ 0 ]
		move( 0, -height / 3.0, kneeFwdMove, knee, r=True, ws=True )

		ankle = createJoint( 'quadAnkle%s' % parityName )
		ankle = cmd.parent( ankle, knee, relative=True )[ 0 ]
		move( 0, -height / 3.0, -kneeFwdMove, ankle, r=True, ws=True )

		toe = createJoint( 'quadToe%s' % parityName )
		toe = cmd.parent( toe, ankle, relative=True )[ 0 ]
		move( 0, -height / 3.0, 0, toe, r=True, ws=True )

		jointSize( thigh, 2 )
		jointSize( ankle, 2 )
		jointSize( toe, 1.5 )

		return [ thigh, knee, ankle, toe ]


#end
