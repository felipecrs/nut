from enum import IntEnum
import Type
import aes128
import Hex
from binascii import hexlify as hx, unhexlify as uhx


class BaseFile:
	def __init__(self, path = None, mode = None, cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		self.offset = 0x0
		self.size = None
		self.f = None
		self.crypto = None
		self.cryptoKey = None
		self.cryptoType = Type.Crypto.NONE
		self.cryptoCounter = None
		self.isPartition = False
		self._path = None
		self._buffer = None
		self._relativePos = 0x0
		self._bufferOffset = 0x0
		self._bufferSize = 0x1000
		self._bufferAlign = 0x1000
		
		if path and mode != None:
			self.open(path, mode, cryptoType, cryptoKey, cryptoCounter)
		
		self.setupCrypto(cryptoType, cryptoKey, cryptoCounter)
			
	def enableBufferedIO(self, size, align = 0):
		self._bufferSize = size
		self._bufferAlign = align
		self._bufferOffset = None
		self._relativePos = 0x0
			
	def partition(self, offset = 0x0, size = None, n = None, cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		if not n:
			n = File()
		#print('partition: ' + str(self) + ', ' + str(n))
			
		n.offset = offset
		
		if not size:
			size = self.size - n.offset - self.offset
			
		n.size = size
		n.f = self
		n.isPartition = True
		
		#print('created partition for %s %x, size = %d' % (n.__class__.__name__, offset, size))
		n.open(None, None, cryptoType, cryptoKey, cryptoCounter)
		
		return n
		
	def read(self, size = None, direct = False):
		if not size:
			size = self.size

		return self.f.read(size)
		
	def readInt8(self, byteorder='little', signed = False):
		return self.read(1)[0]
		
	def readInt16(self, byteorder='little', signed = False):
		return int.from_bytes(self.read(2), byteorder=byteorder, signed=signed)
		
	def readInt32(self, byteorder='little', signed = False):
		return int.from_bytes(self.read(4), byteorder=byteorder, signed=signed)
		
	def readInt64(self, byteorder='little', signed = False):
		return int.from_bytes(self.read(8), byteorder=byteorder, signed=signed)
		
	def write(self, buffer):
		return self.f.write(buffer)
	
	def seek(self, offset, from_what = 0):
		if not self.isOpen():
			raise IOError('Trying to seek on closed file')

		if from_what == 0:
			# seek from begining				
			self.f.seek(self.offset + offset)
			#if self.cryptoType == Type.Crypto.CTR:
			#	self.crypto.set_ctr(self.setCounter(self.offset + self.tell()))
			return
		elif from_what == 1:
			# seek from current position
			self.f.seek(self.offset + offset)

			#if self.cryptoType == Type.Crypto.CTR:
			#	self.crypto.set_ctr(self.setCounter(self.offset + self.tell()))
			return
		elif from_what == 2:
			# see from end
			if offset > 0:
				raise Exception('Invalid seek offset')

			self.f.seek(self.offset + offset + self.size)

			#if self.cryptoType == Type.Crypto.CTR:
			#	self.crypto.set_ctr(self.setCounter(self.offset + self.tell()))
			return
			
		raise Exception('Invalid seek type')
		
	def rewind(self, offset = None):
		if offset:
			self.seek(-offset, 1)
		else:
			self.seek(0)
			
	def setupCrypto(self, cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		if cryptoType != -1:
			self.cryptoType = cryptoType
			
		if cryptoKey != -1:
			self.cryptoKey = cryptoKey
			
		if cryptoCounter != -1:
			self.cryptoCounter = cryptoCounter
			
		if self.cryptoType == Type.Crypto.CTR:
			#print('setting up ctr')
			#self.rewind()
			self.crypto = aes128.AESCTR(self.cryptoKey, self.setCounter(self.offset))
			self.cryptoType = Type.Crypto.CTR
			
			self.enableBufferedIO(0x10, 0x10)

			#self.__class__ = AesCtrFile
		elif self.cryptoType == Type.Crypto.XTS:
			#print('setting up xts')
			self.crypto = aes128.AESXTS(self.cryptoKey)
			self.cryptoType = Type.Crypto.XTS
			
			if self.size < 1 or self.size > 0xFFFFFF:
				raise IOError('AESXTS Block too large or small')
			
			self.rewind()
			self.enableBufferedIO(self.size, 0x10)
			#self.__class__ = AesXtsFile
		elif self.cryptoType == Type.Crypto.BKTR:
			self.cryptoType = Type.Crypto.BKTR
		elif self.cryptoType == Type.Crypto.NCA0:
			self.cryptoType = Type.Crypto.NCA0
		elif self.cryptoType == Type.Crypto.NONE:
			self.cryptoType = Type.Crypto.NONE


	def open(self, path, mode = 'rb', cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		if path != None:
			if self.isOpen():
				self.close()
				
			if isinstance(path, str):
				self.f = open(path, mode)
				self._path = path
				
				self.f.seek(0,2)
				self.size = self.f.tell()
				self.f.seek(0,0)
			elif isinstance(path, BaseFile):
				self.f = path
				self.size = path.size
			else:
				raise IOError('Invalid file parameter')

		
		self.setupCrypto(cryptoType, cryptoKey, cryptoCounter)
		
	def close(self):
		self.f.close()
		self.f = None
		
	def tell(self):
		return self.f.tell() - self.offset
		
	def isOpen(self):
		return self.f != None
		
	def setCounter(self, ofs):
		ctr = self.cryptoCounter.copy()
		ofs >>= 4
		for j in range(8):
			ctr[0x10-j-1] = ofs & 0xFF
			ofs >>= 8
		return bytes(ctr)
		
	def printInfo(self, indent = 0):
		tabs = '\t' * indent
		if self._path:
			print('%sFile Path: %s' % (tabs, self._path))
		print('%sFile Size: %s' % (tabs, self.size))


class BufferedFile(BaseFile):
	def __init__(self, path = None, mode = None, cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		super(BufferedFile, self).__init__(path, mode, cryptoType, cryptoKey, cryptoCounter)

	def read(self, size = None, direct = False):
		if not size:
			size = self.size

		if self._bufferOffset == None or self._buffer == None or self._relativePos < self._bufferOffset or (self._relativePos + size)  > self._bufferOffset + len(self._buffer):
			#self._bufferOffset = self._relativePos & ~(self._bufferAlign-1)
			self._bufferOffset = (int(self._relativePos / self._bufferAlign) * self._bufferAlign)

			pageReadSize = self._bufferSize

			while self._relativePos + size > self._bufferOffset + pageReadSize:
				pageReadSize += self._bufferSize

			#print('disk read %s\t\t: relativePos = %x, bufferOffset = %x, align = %x, size = %x, pageReadSize = %x, bufferSize = %x' % (self.__class__.__name__, self._relativePos, self._bufferOffset, self._bufferAlign, size, pageReadSize, self._bufferSize))
			super(BufferedFile, self).seek(self._bufferOffset)
			#self.seek(self._bufferOffset)
			self._buffer = super(BufferedFile, self).read(pageReadSize)
			self.pageRefreshed()
			if len(self._buffer) == 0:
				raise IOError('read returned empty ' + hex(self.offset))
				
		offset = self._relativePos - self._bufferOffset
		r = self._buffer[offset:offset+size]
		self._relativePos += size
		return r

	def pageRefreshed(self):
		pass

	def tell(self):
		return self._relativePos

	def seek(self, offset, from_what = 0):
		if not self.isOpen():
			raise IOError('Trying to seek on closed file')

		f = self.f
		

		if from_what == 0:
			# seek from begining
			self._relativePos = offset
			return

		elif from_what == 1:
			# seek from current position
			if self._buffer:
				self._relativePos += offset
				return
			
			r = f.seek(self.offset + offset)				
			return r

		elif from_what == 2:
			# see from end
			if offset > 0:
				raise Exception('Invalid seek offset')
			self._relativePos = self.size + offset
			return
			
		raise Exception('Invalid seek type')

class File(BufferedFile):
	def __init__(self, path = None, mode = None, cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		super(File, self).__init__(path, mode, cryptoType, cryptoKey, cryptoCounter)

	def pageRefreshed(self):
		if self.crypto:
			if self.cryptoType == Type.Crypto.CTR:
				#print('reading ctr from ' + hex(self._bufferOffset))
				self.crypto.set_ctr(self.setCounter(self.offset + self._bufferOffset))
			else:
				pass
				#print('reading from ' + hex(self._bufferOffset))
			self._buffer = self.crypto.decrypt(self._buffer)
		return self._buffer
		
class CryptoFile(BufferedFile):
	def __init__(self, path = None, mode = None, cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		super(CryptoFile, self).__init__(path, mode, cryptoType, cryptoKey, cryptoCounter)

	def pageRefreshed(self):
		self._buffer = self.crypto.decrypt(self._buffer)
		return self._buffer

	def read2(self, size = None, direct = False):
		return self.crypto.decrypt(super(CryptoFile, self).read(size))

class AesXtsFile(CryptoFile):
	def __init__(self, path = None, mode = None, cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		super(AesXtsFile, self).__init__(path, mode, cryptoType, cryptoKey, cryptoCounter)

class AesCtrFile(CryptoFile):
	def __init__(self, path = None, mode = None, cryptoType = -1, cryptoKey = -1, cryptoCounter = -1):
		super(AesCtrFile, self).__init__(path, mode, cryptoType, cryptoKey, cryptoCounter)

