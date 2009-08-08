import string

class Name(object):
	'''Name objects are strings that are used to identify something such as an object or a filepath.
	this class creates some useful ways of comparing and manipulating Name objects'''

	__slots__ = ['string','prefixDelimeters','punctuation','prefix']
	def __init__( self, theString='' ):
		self.string = theString
		self.prefix = None
		self.prefixDelimeters = ':'
		self.punctuation = '_.'
	def __repr__( self ):
		return self.string
	def __str__( self ):
		return self.string
	def __eq__( self, other ):
		return self.likeness(other)
	def cache_prefix( self, delimeters=None ):
		'''strips any namespace or path data from the name string - by default the stripping is done
		"in place", but if the inPlace variable is set to true, then a new Name object is returned'''
		self.prefix = ''
		string = self.string.strip()
		lastMatch = -1
		if delimeters == None:
			delimeters = self.prefixDelimeters

		for char in delimeters:
			matchPos = string.rfind(char)
			if matchPos > lastMatch:
				lastMatch = matchPos

		#store the prefix string
		if lastMatch != -1:
			self.prefix = string[:lastMatch+1]

		return self.prefix
	def uncache_prefix( self ):
		if self.prefix != None:
			self.string = self.prefix + self.string

		return self.string
	def get_prefix( self, delimeters=None ):
		'''strips any namespace or path data from the name string - by default the stripping is done
		"in place", but if the inPlace variable is set to true, then a new Name object is returned'''
		if self.prefix == None: return self.cache_prefix(delimeters)
		else: return self.prefix
	def likeness( self, other ):
		'''given two Name objects this method will return a "likeness" factor based on how similar
		the two name strings are.  it compares name tokens - tokens are defined by either camel case
		or any character defined in the self.punctuation variable.  so for example:
		thisStringHas_a_fewTokens

		has the tokens this, String, Has, a, few, Tokens'''
		#if the names match exactly, return the highest likeness
		if self.string == other.string: return 1.0

		srcTokens = self.split()
		tgtTokens = other.split()

		#if the split result is exact, early out
		if srcTokens == tgtTokens: return 1.0

		exactMatchWeight = 1.025
		totalWeight = 0
		numSrcToks,numTgtToks = len(srcTokens),len(tgtTokens)

		for srcTok in srcTokens:
			bestMatch,bestMatchIdx = 0,-1
			for n in range(numTgtToks):
				tgtTok = tgtTokens[n]
				tokSize = len(tgtTok)
				isSrcDigit = srcTok.isdigit()
				isTgtDigit = tgtTok.isdigit()

				#if one is a number token and the other isn't - there is no point proceeding as they're not going to match
				#letter tokens should not match number tokens - i guess it would be possible to test whether the word token
				#was a number name, but this would be expensive, and would only help fringe cases
				if isSrcDigit or isTgtDigit:
					break

				#first, check to see if the names are the same
				if srcTok == tgtTok:
					bestMatch = tokSize * exactMatchWeight
					bestMatchIdx = n
					break

				#are the tokens numeric tokens?  if so, we need to figure out how similar they are numerically - numbers that are closer to one another should result in a better match
				elif isSrcDigit and isTgtDigit:
					srcInt,tgtInt = int(srcTok),int(tgtTok)
					largest = max( abs(srcInt), abs(tgtInt) )
					closeness = 1

					if srcInt != tgtInt: closeness = ( largest - abs( srcInt-tgtInt ) ) / float(largest)
					bestMatch = tokSize * closeness
					bestMatchIdx = n
					break

				#are the names the same bar case differences?
				elif srcTok.lower() == tgtTok.lower():
					bestMatch = tokSize
					bestMatchIdx = n
					break

				#so now test to see if any of the tokens are "sub-words" of each other - ie if you have something_otherThing another_other
				#the second token, "otherThing" and "other", the second is a subset of the first, so this is a rough match
				else:
					srcTokSize = len(srcTok)
					lowSrcTok,lowTgtTok = srcTok.lower(),tgtTok.lower()
					smallestWordSize = min( srcTokSize, tokSize )
					subWordWeight = 0

					#the weight is calculated as a percentage of matched letters
					if srcTokSize > tokSize: subWordWeight = tokSize * tokSize / float(srcTokSize)
					else: subWordWeight = srcTokSize * srcTokSize / float(tokSize)

					if srcTokSize > 1 and tokSize > 1:
						#make sure the src and tgt tokens are non-trivial (ie at least 2 letters)
						if lowSrcTok.find(lowTgtTok) != -1 or lowTgtTok.find(lowSrcTok) != -1:
							bestMatch = subWordWeight
							bestMatchIdx = n

			#remove the best match from the list - so it doesn't get matched to any other tokens
			if bestMatchIdx != -1:
				tgtTokens.pop(bestMatchIdx)
				numTgtToks -= 1

			totalWeight += bestMatch

		#get the total number of letters in the "words" of the longest name - we use this for a likeness baseline
		lenCleanSrc = len(self.string)-self.string.count('_')
		lenCleanTgt = len(other.string)-other.string.count('_')
		lenClean = max( lenCleanSrc, lenCleanTgt )

		return totalWeight / ( lenClean*exactMatchWeight )
	def strip( self, inPlace=True ):
		'''strips any namespace or path data from the name string - by default the stripping is done
		"in place", but if the inPlace variable is set to true, then a new Name object is returned'''
		#prefix = self.get_prefix()
		string = self.string.strip()
		for char in self.prefixDelimeters:
			lastMatch = string.rfind(char)
			if lastMatch != -1:
				string = string[lastMatch+1:]

		#if we're to perform the operation in place, then modify the self.string variable and return
		if inPlace:
			self.string = string
			return self

		new = self.__new__(self.__class__)
		new.__init__(string)

		return new
	def split( self, aString=None ):
		'''retuns a list of name tokens.  tokens are delimited by either camel case separation,
		digit grouping, or any character present in the self.punctuation variable - the list of
		tokens is returned'''
		if aString == None: aString = self.string

		tokens = [aString[0]]
		prevCharCaseWasLower = aString[0].islower()
		prevCharWasDigit = aString[0].isdigit()

		#step through the string and look for token split cases
		for char in aString[1:]:
			isLower = char.islower()
			if char in self.punctuation:
				tokens.append('')
				prevCharCaseWasLower = True
				prevCharWasDigit = False
				continue
			if char.isdigit():
				if prevCharWasDigit: tokens[-1] += char
				else: tokens.append(char)
				prevCharCaseWasLower = True
				prevCharWasDigit = True
				continue
			if prevCharWasDigit:
				tokens.append(char)
				prevCharWasDigit = False
				prevCharCaseWasLower = isLower
				continue
			elif prevCharCaseWasLower and not isLower: tokens.append(char)
			else: tokens[-1] += char

			prevCharWasDigit = False
			prevCharCaseWasLower = isLower

		#finally get rid of any empty/null array entries - this could be done above but is easier (maybe even faster?) to do as a post step
		return [tok for tok in tokens if tok ]

	
def matchNames( srcList, tgtList, strip=True, parity=False, unique=True, opposite=False, threshold=0 ):
	'''given two lists of strings, this method will return a list (the same size as the first - source list)
	with the most appropriate matches found in the second (target) list'''
	#build the Name objects for the strings
	srcNames = [ Name(name) for name in srcList ]
	tgtNames = [ Name(name) for name in tgtList ]
	numSrc,numTgt = len(srcList),len(tgtList)
	emptyName = Name()

	#cache prefixes so they don't affect name matching - caching them stores them on the name instance so we can retrieve them later
	if strip:
		for a in srcNames: a.cache_prefix()
		for a in tgtNames: a.cache_prefix()

	matches = []
	for name in srcNames:
		foundExactMatch = False
		likenessList = []
		n = 0
		for tgt in tgtNames:
			likeness = name.likeness(tgt)
			if likeness == 1:
				matches.append(tgt)
				tgtNames.pop(n)
				foundExactMatch = True
				break

			likenessList.append(likeness)
			n += 1

		#early out
		if foundExactMatch:
			continue

		#find the idx of the highest likeness
		bestIdx = 0
		for n in range(len(likenessList)):
			if likenessList[n] > likenessList[bestIdx]: bestIdx = n

		if likenessList[bestIdx] > threshold:
			#are we performing unique matching?  if so, remove the best target match from the target list
			if unique: matches.append(tgtNames.pop(bestIdx))
			else: matches.append(tgtNames[bestIdx])
		else: matches.append(emptyName)

	#re-apply any prefixes we stripped
	print matches
	if strip: matches = [ a.uncache_prefix() for a in matches ] #map(lambda a,b: a+b,tgtPrefixes,matches)

	#collapse back to strings - matchNames takes strings and returns strings
	#matches = [ a.string for a in matches ]

	return matches


def test():
	name1 = Name('thisISaString_with_Some_tokensYeah')
	name2 = Name('thisISaString123')
	splitTestA = name1.split()
	splitTestB = name2.split()

	if splitTestA != ['this','ISa','String','with','Some','tokens','Yeah']:
		print 'split testA is failing',splitTestA
	else: print 'testA success!'
	if splitTestB != ['this','ISa','String','123']:
		print 'split testB is failing',splitTestB
	else: print 'testB success!'

	a = ["main","UpperbodyControl","PelvisControl","Ref:prp_hippouch_0_L_Control",\
		 "Ref:prp_hippouch_0_BControl","Ref:bip_spine_0FKcontrol","Ref:bip_spine_1FKcontrol",\
		 "Ref:bip_spine_2FKcontrol","Ref:bip_spine_3FKcontrol","ikChest","Ref:bip_hip_L_FK",\
		 "Ref:bip_knee_L_FK","Ref:bip_foot_L_FK","Ref:bip_toe_L_FK","Ref:bip_hip_R_FK",\
		 "Ref:bip_knee_R_FK","Ref:bip_foot_R_FK","Ref:bip_toe_R_FK","coatL_Control","coatR_Control",\
		 "L_ShoulderControl","Ref:bip_upperArm_L_FK","Ref:bip_lowerArm_L_FK","Ref:bip_hand_L_FK",\
		 "R_ShoulderControl","Ref:bip_upperArm_R_FK","Ref:bip_lowerArm_R_FK","Ref:bip_hand_R_FK",\
		 "neckControl","headControl","Ref:prp_glassesControl","L_ikHandControl","L_HandControl",\
		 "L_FootControl","L_ToeControl","R_ikHandControl","R_HandControl","R_FootControl","R_ToeControl",\
		 "rkneeControl","lkneeControl","L_ElbowControl","R_ElbowControl","Ref:prp_coat_front_1_L_Control",\
		 "Ref:prp_coat_front_2_L_Control","Ref:prp_coat_front_1_R_Control","Ref:prp_coat_front_2_R_Control",\
		 "Ref:prp_coat_back_0_L_Control","Ref:prp_coat_back_1_L_Control","Ref:prp_coat_back_2_L_Control",\
		 "Ref:prp_coat_back_0_MControl","Ref:prp_coat_back_1_MControl","Ref:prp_coat_back_2_MControl",\
		 "Ref:prp_coat_back_0_R_Control","Ref:prp_coat_back_1_R_Control","Ref:prp_coat_back_2_R_Control",\
		 "Ref:bip_thumb_0_L_Control","Ref:bip_thumb_1_L_Control","Ref:bip_thumb_2_L_Control",\
		 "Ref:bip_index_0_L_Control","Ref:bip_index_1_L_Control","Ref:bip_index_2_L_Control",\
		 "Ref:bip_middle_0_L_Control","Ref:bip_middle_1_L_Control","Ref:bip_middle_2_L_Control",\
		 "Ref:bip_ring_0_L_Control","Ref:bip_ring_1_L_Control","Ref:bip_ring_2_L_Control",\
		 "Ref:bip_pinky_0_L_Control","Ref:bip_pinky_1_L_Control","Ref:bip_pinky_2_L_Control",\
		 "Ref:bip_thumb_0_R_Control","Ref:bip_thumb_1_R_Control","Ref:bip_thumb_2_R_Control",\
		 "Ref:bip_index_0_R_Control","Ref:bip_index_1_R_Control","Ref:bip_index_2_R_Control",\
		 "Ref:bip_middle_0_R_Control","Ref:bip_middle_1_R_Control","Ref:bip_middle_2_R_Control",\
		 "Ref:bip_ring_0_R_Control","Ref:bip_ring_1_R_Control","Ref:bip_ring_2_R_Control",\
		 "Ref:bip_pinky_0_R_Control","Ref:bip_pinky_1_R_Control","Ref:bip_pinky_2_R_Control"]

	b = ["main","Upperbody_Control","Pelvis_Control","hippouch_0_L_Control",\
		 "hippouch_0_BControl","spine_0_fkcontrol","spine_1_fkcontrol",\
		 "spine_2_fkcontrol","spine_3_fkcontrol","ikChest","hip_L_fk",\
		 "knee_L_fk","foot_L_fk","toe_L_fk","hip_R_fk",\
		 "knee_R_fk","foot_R_fk","toe_R_fk","coatL_Control","coatR_Control",\
		 "L_ShoulderControl","upperArm_L_fk","lowerArm_L_fk","hand_L_fk",\
		 "R_ShoulderControl","upperArm_R_fk","lowerArm_R_fk","hand_R_fk",\
		 "neckControl","headControl","glassesControl","L_ikHandControl","L_HandControl",\
		 "L_FootControl","L_ToeControl","R_ikHandControl","R_HandControl","R_FootControl","R_ToeControl",\
		 "rkneeControl","lkneeControl","L_ElbowControl","R_ElbowControl","coat_front_1_L_Control",\
		 "coat_front_2_L_Control","coat_front_1_R_Control","coat_front_2_R_Control",\
		 "coat_back_0_L_Control","coat_back_1_L_Control","coat_back_2_L_Control",\
		 "coat_back_0_m_control","coat_back_1_m_control","coat_back_2_m_control",\
		 "coat_back_0_R_Control","coat_back_1_R_Control","coat_back_2_R_Control",\
		 "thumb_0_L_Control","thumb_1_L_Control","thumb_2_L_Control",\
		 "index_0_L_Control","index_1_L_Control","index_2_L_Control",\
		 "middle_0_L_Control","middle_1_L_Control","middle_2_L_Control",\
		 "ring_0_L_Control","ring_1_L_Control","ring_2_L_Control",\
		 "pinky_0_L_Control","pinky_1_L_Control","pinky_2_L_Control",\
		 "thumb_0_R_Control","thumb_1_R_Control","thumb_2_R_Control",\
		 "index_0_R_Control","index_1_R_Control","index_2_R_Control",\
		 "middle_0_R_Control","middle_1_R_Control","middle_2_R_Control",\
		 "ring_0_R_Control","ring_1_R_Control","ring_2_R_Control",\
		 "pinky_0_R_Control","pinky_1_R_Control","pinky_2_R_Control"]

	print matchNames( a, b )


def test2():
	a = ["Bip01","Bip01_Pelvis",\
			"Bip01_Spine","Bip01_Spine1","Bip01_Spine2","Bip01_Spine3","Bip01_Spine4",\
			"Bip01_Neck1","Bip01_Head1",\
			"Bip01_L_Clavicle","Bip01_L_UpperArm","Bip01_L_Forearm","Bip01_L_Hand",\
			"Bip01_R_Clavicle","Bip01_R_UpperArm","Bip01_R_Forearm","Bip01_R_Hand",\

			"Bip01_L_Finger1","Bip01_L_Finger11","Bip01_L_Finger12",\
			"Bip01_L_Finger2","Bip01_L_Finger21","Bip01_L_Finger22",\
			"Bip01_L_Finger3","Bip01_L_Finger31","Bip01_L_Finger32",\
			"Bip01_L_Finger4","Bip01_L_Finger41","Bip01_L_Finger42",\
			"Bip01_L_Finger0","Bip01_L_Finger01","Bip01_L_Finger02",\
			"Bip01_R_Finger1","Bip01_R_Finger11","Bip01_R_Finger12",\
			"Bip01_R_Finger2","Bip01_R_Finger21","Bip01_R_Finger22",\
			"Bip01_R_Finger3","Bip01_R_Finger31","Bip01_R_Finger32",\
			"Bip01_R_Finger4","Bip01_R_Finger41","Bip01_R_Finger42",\
			"Bip01_R_Finger0","Bip01_R_Finger01","Bip01_R_Finger02",\

			"Bip01_L_Foot","Bip01_L_Calf",\
			"Bip01_R_Foot","Bip01_R_Calf"]

	b=['Bip01_L_Toe0', 'Bip01_L_Foot', 'Bip01_L_Ankle', 'Bip01_L_Shin', 'Bip01_L_Calf', 'Bip01_L_Knee', 'Bip01_L_Quadricep', 'Bip01_L_Thigh', u'Bip01_R_Toe0', u'Bip01_R_Foot', u'Bip01_R_Ankle', u'Bip01_R_Shin', u'Bip01_R_Calf', u'Bip01_R_Quadricep', u'Bip01_R_Knee', u'Bip01_R_Thigh', u'Bip01_Pelvis', u'Bip01_Head1', u'Bip01_Neck1', u'Bip01_L_Finger42', u'Bip01_L_Finger41', u'Bip01_L_Finger4', u'Bip01_L_Finger32', u'Bip01_L_Finger31', u'Bip01_L_Finger3', u'Bip01_L_Finger22', u'Bip01_L_Finger21', u'Bip01_L_Finger2', u'Bip01_L_Finger12', u'Bip01_L_Finger11', u'Bip01_L_Finger1', u'Bip01_L_Finger02', u'Bip01_L_Finger01', u'Bip01_L_Finger0', u'Bip01_L_Hand', u'Bip01_L_Ulna', u'Bip01_L_Wrist', u'Bip01_L_Forearm', u'Bip01_L_Shoulder', u'Bip01_L_Elbow', u'Bip01_L_Bicep', u'Bip01_L_UpperArm', u'Bip01_L_Trapezius', u'Bip01_L_shoulderBlade', u'Bip01_L_Clavicle', u'Bip01_R_Finger42', u'Bip01_R_Finger41', u'Bip01_R_Finger4', u'Bip01_R_Finger32', u'Bip01_R_Finger31', u'Bip01_R_Finger3', u'Bip01_R_Finger22', u'Bip01_R_Finger21', u'Bip01_R_Finger2', u'Bip01_R_Finger12', u'Bip01_R_Finger11', u'Bip01_R_Finger1', u'Bip01_R_Finger02', u'Bip01_R_Finger01', u'Bip01_R_Finger0', u'Bip01_R_Hand', u'Bip01_R_Wrist', u'Bip01_R_Ulna', u'Bip01_R_Forearm', u'Bip01_R_Bicep', u'Bip01_R_Shoulder', u'Bip01_R_Elbow', u'Bip01_R_UpperArm', u'Bip01_R_Trapezius', u'Bip01_R_shoulderBlade', u'Bip01_R_Clavicle', u'Bip01_Spine4', u'Bip01_L_Latt', u'Bip01_R_Pectoral', u'Bip01_R_Latt', u'Bip01_L_Pectoral', u'Jacket0_bone', u'Jacket1_bone', u'Bip01_Spine2', u'Bip01_Spine1', u'Bip01_Spine', u'Bip01']

	c = matchNames(a,b,parity=True,threshold=0.5)
	for n in range(len(c)):
		print c[n],'->',a[n]


if __name__ == '__main__':
	test()


#end