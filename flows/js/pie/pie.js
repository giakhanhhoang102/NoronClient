const { createPanProtector } = require('./pan-protector.full');

const protector = createPanProtector({
  L: 6,
  E: 4,
  K: '00112233445566778899aabbccddeeff', // 32 hex
  key_id: '01ab23cd',                    // 8 hex
  phase: 0
});

const { s, q, mac } = protector.protectPANandCVV('4111 1111 1111 1111', '123', false);
if (!protector.verifyIntegrity('00112233445566778899aabbccddeeff', s, q, mac)) {
  throw new Error('MAC mismatch!');
}
