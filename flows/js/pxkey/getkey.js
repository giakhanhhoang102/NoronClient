function encode(input, shift) {
    let encoded = '';
    for (let i = 0; i < input.length; i++) {
      let charCode = input.charCodeAt(i);
      let newCharCode = charCode + 3;
      encoded += String.fromCharCode(newCharCode);
    }
    return encoded;
  }
const authKey = "PX-BD8934DE-2BB3-47F0-B7C5-F0C47BA2B9F2";
const shift = 3;
const encodedAuthKey = encode(authKey, shift);

console.log(encodedAuthKey);