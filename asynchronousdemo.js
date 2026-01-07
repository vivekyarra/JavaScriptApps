console.log("first");

setTimeout(function () {
  console.log("second");
}, 2000);

setTimeout(() => {
  console.log("third");
}, 0);

console.log("four");
