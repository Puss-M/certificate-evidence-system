const VERSION = 5
const SIZE = VERSION * 4 + 17
const DATA_CODEWORDS = 108
const ECC_CODEWORDS = 26

type Matrix = number[][]

class BitBuffer {
  bits: number[] = []

  append(value: number, length: number) {
    for (let i = length - 1; i >= 0; i -= 1) this.bits.push((value >>> i) & 1)
  }
}

function utf8Bytes(text: string) {
  return Array.from(new TextEncoder().encode(text))
}

function makeDataCodewords(text: string) {
  const bytes = utf8Bytes(text)
  const buffer = new BitBuffer()
  buffer.append(0b0100, 4)
  buffer.append(bytes.length, 8)
  bytes.forEach(byte => buffer.append(byte, 8))
  const capacityBits = DATA_CODEWORDS * 8
  if (buffer.bits.length > capacityBits) {
    throw new Error('QR content is too long')
  }
  buffer.append(0, Math.min(4, capacityBits - buffer.bits.length))
  while (buffer.bits.length % 8) buffer.append(0, 1)

  const data: number[] = []
  for (let i = 0; i < buffer.bits.length; i += 8) {
    data.push(buffer.bits.slice(i, i + 8).reduce((sum, bit) => (sum << 1) | bit, 0))
  }
  for (let pad = 0; data.length < DATA_CODEWORDS; pad += 1) data.push(pad % 2 ? 0x11 : 0xec)
  return data
}

const gfExp: number[] = Array(512).fill(0)
const gfLog: number[] = Array(256).fill(0)
let gfReady = false

function initGf() {
  if (gfReady) return
  let value = 1
  for (let i = 0; i < 255; i += 1) {
    gfExp[i] = value
    gfLog[value] = i
    value <<= 1
    if (value & 0x100) value ^= 0x11d
  }
  for (let i = 255; i < 512; i += 1) gfExp[i] = gfExp[i - 255]
  gfReady = true
}

function gfMul(a: number, b: number) {
  if (!a || !b) return 0
  return gfExp[gfLog[a] + gfLog[b]]
}

function generatorPoly(degree: number) {
  initGf()
  let poly = [1]
  for (let i = 0; i < degree; i += 1) {
    const next = Array(poly.length + 1).fill(0)
    poly.forEach((coefficient, index) => {
      next[index] ^= coefficient
      next[index + 1] ^= gfMul(coefficient, gfExp[i])
    })
    poly = next
  }
  return poly
}

function reedSolomon(data: number[], degree: number) {
  const gen = generatorPoly(degree)
  const ecc = Array(degree).fill(0)
  data.forEach(byte => {
    const factor = byte ^ ecc[0]
    ecc.shift()
    ecc.push(0)
    for (let i = 0; i < degree; i += 1) ecc[i] ^= gfMul(gen[i + 1], factor)
  })
  return ecc
}

function createMatrix() {
  return {
    modules: Array.from({ length: SIZE }, () => Array(SIZE).fill(0)) as Matrix,
    reserved: Array.from({ length: SIZE }, () => Array(SIZE).fill(false)) as boolean[][],
  }
}

function setModule(modules: Matrix, reserved: boolean[][], x: number, y: number, dark: boolean, lock = true) {
  if (x < 0 || y < 0 || x >= SIZE || y >= SIZE) return
  modules[y][x] = dark ? 1 : 0
  if (lock) reserved[y][x] = true
}

function addFinder(modules: Matrix, reserved: boolean[][], x: number, y: number) {
  for (let dy = -1; dy <= 7; dy += 1) {
    for (let dx = -1; dx <= 7; dx += 1) {
      const xx = x + dx
      const yy = y + dy
      const inFinder = dx >= 0 && dx <= 6 && dy >= 0 && dy <= 6
      const dark = inFinder && (dx === 0 || dx === 6 || dy === 0 || dy === 6 || (dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4))
      setModule(modules, reserved, xx, yy, dark)
    }
  }
}

function addAlignment(modules: Matrix, reserved: boolean[][], cx: number, cy: number) {
  for (let dy = -2; dy <= 2; dy += 1) {
    for (let dx = -2; dx <= 2; dx += 1) {
      const distance = Math.max(Math.abs(dx), Math.abs(dy))
      setModule(modules, reserved, cx + dx, cy + dy, distance !== 1)
    }
  }
}

function reserveFormatAreas(reserved: boolean[][]) {
  for (let i = 0; i <= 8; i += 1) {
    if (i !== 6) {
      reserved[8][i] = true
      reserved[i][8] = true
    }
  }
  for (let i = 0; i < 8; i += 1) reserved[8][SIZE - 1 - i] = true
  for (let i = 0; i < 7; i += 1) reserved[SIZE - 1 - i][8] = true
}

function addPatterns(modules: Matrix, reserved: boolean[][]) {
  addFinder(modules, reserved, 0, 0)
  addFinder(modules, reserved, SIZE - 7, 0)
  addFinder(modules, reserved, 0, SIZE - 7)
  for (let i = 8; i < SIZE - 8; i += 1) {
    setModule(modules, reserved, i, 6, i % 2 === 0)
    setModule(modules, reserved, 6, i, i % 2 === 0)
  }
  addAlignment(modules, reserved, 30, 30)
  setModule(modules, reserved, 8, VERSION * 4 + 9, true)
  reserveFormatAreas(reserved)
}

function maskBit(x: number, y: number) {
  return (x + y) % 2 === 0
}

function addCodewords(modules: Matrix, reserved: boolean[][], codewords: number[]) {
  const bits = codewords.flatMap(byte => Array.from({ length: 8 }, (_, i) => (byte >>> (7 - i)) & 1))
  let bitIndex = 0
  let upward = true
  for (let x = SIZE - 1; x > 0; x -= 2) {
    if (x === 6) x -= 1
    for (let offset = 0; offset < SIZE; offset += 1) {
      const y = upward ? SIZE - 1 - offset : offset
      for (let dx = 0; dx < 2; dx += 1) {
        const xx = x - dx
        if (reserved[y][xx]) continue
        const raw = bitIndex < bits.length ? bits[bitIndex] : 0
        bitIndex += 1
        modules[y][xx] = raw ^ (maskBit(xx, y) ? 1 : 0)
      }
    }
    upward = !upward
  }
}

function bchFormat(value: number) {
  let data = value << 10
  const generator = 0b10100110111
  for (let i = 14; i >= 10; i -= 1) {
    if ((data >>> i) & 1) data ^= generator << (i - 10)
  }
  return ((value << 10) | data) ^ 0b101010000010010
}

function addFormat(modules: Matrix, reserved: boolean[][]) {
  const bits = bchFormat(0b01000)
  const bit = (i: number) => Boolean((bits >>> i) & 1)

  for (let i = 0; i <= 5; i += 1) setModule(modules, reserved, 8, i, bit(i), false)
  setModule(modules, reserved, 8, 7, bit(6), false)
  setModule(modules, reserved, 8, 8, bit(7), false)
  setModule(modules, reserved, 7, 8, bit(8), false)
  for (let i = 9; i < 15; i += 1) setModule(modules, reserved, 14 - i, 8, bit(i), false)

  for (let i = 0; i < 8; i += 1) setModule(modules, reserved, SIZE - 1 - i, 8, bit(i), false)
  for (let i = 8; i < 15; i += 1) setModule(modules, reserved, 8, SIZE - 15 + i, bit(i), false)
}

export function makeQrSvgDataUrl(text: string, moduleSize = 6) {
  const data = makeDataCodewords(text)
  const ecc = reedSolomon(data, ECC_CODEWORDS)
  const { modules, reserved } = createMatrix()
  addPatterns(modules, reserved)
  addCodewords(modules, reserved, [...data, ...ecc])
  addFormat(modules, reserved)

  const quiet = 4
  const total = (SIZE + quiet * 2) * moduleSize
  const rects: string[] = []
  modules.forEach((row, y) => {
    row.forEach((dark, x) => {
      if (dark) rects.push(`<rect x="${(x + quiet) * moduleSize}" y="${(y + quiet) * moduleSize}" width="${moduleSize}" height="${moduleSize}"/>`)
    })
  })
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${total} ${total}" width="${total}" height="${total}"><rect width="100%" height="100%" fill="#fff"/><g fill="#0f172a">${rects.join('')}</g></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}
