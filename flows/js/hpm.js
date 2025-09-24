const crypto = require('crypto');

function toPemPublicKey(rawOrPem){
  const s = String(rawOrPem||'').trim();
  if (s.includes('-----BEGIN')) return s;
  const b64 = s.replace(/\s+/g,'');
  const lines = b64.match(/.{1,64}/g) || [b64];
  return `-----BEGIN PUBLIC KEY-----\n${lines.join('\n')}\n-----END PUBLIC KEY-----`;
}

function buildEncryptedValuesOfficial(pemKey, {ccNum, cvv, mm, yyyy}){
  const plain = `#${ccNum}#${cvv}#${mm}#${yyyy}`;
  const b64Plain = Buffer.from(plain,'utf8').toString('base64');
  const buf = Buffer.from(b64Plain,'utf8');
  const pub = crypto.createPublicKey({ key: pemKey, format: 'pem', type: 'spki' });
  const encrypted = crypto.publicEncrypt({ key: pub, padding: crypto.constants.RSA_PKCS1_PADDING }, buf);
  return encrypted.toString('base64');
}

function main(){
  let args={};
  try{ args = JSON.parse(process.argv[2]||'{}'); }catch{}
  const FIELD_KEY = (args.field_key||'').trim();
  if (!FIELD_KEY) { process.stderr.write('Missing field_key'); process.exit(1); }
  const ccNum = String(args.CCNUM||'4111111111111111').replace(/\s+/g,'');
  const cvv   = String(args.CCV  ||'123').replace(/\s+/g,'');
  const mm    = String(args.MM   ||'09');
  const yyyy  = String(args.YYYY ||'2027');

  const pem = toPemPublicKey(FIELD_KEY);
  const encrypted_fields = '#field_creditCardNumber#field_cardSecurityCode#field_creditCardExpirationMonth#field_creditCardExpirationYear';
  const encrypted_values = buildEncryptedValuesOfficial(pem, {ccNum, cvv, mm, yyyy});
  if ((args.only||'').toLowerCase()==='encrypted_values'){
    process.stdout.write(encrypted_values);
    return;
  }
  const out = { encrypted_fields, encrypted_values };
  process.stdout.write(JSON.stringify(out));
}

main();
