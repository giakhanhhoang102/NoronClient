const crypto = require('crypto');

function main(){
  let args = {};
  try{ args = JSON.parse(process.argv[2]||'{}'); }catch{}
  const methodData = {
    cvv: String(args.CCV||''),
    expiration_month: String(args.MM||''),
    expiration_year: String(args.YYYY||''),
    full_number: String(args.CCNUM||''),
    gateway_handle: 'stripe-us'
  };

  const SEP = '\uFFA0';
  const joined = Object.keys(methodData)
    .sort()
    .map(k => String(methodData[k] ?? ''))
    .join(SEP);

  const result = crypto.createHash('sha1').update(joined, 'utf8').digest('hex');
  process.stdout.write(JSON.stringify({result}));
}

main();