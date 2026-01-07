// datatypes in javascript (single line comments)
var empid = 1001;
console.log(typeof empid); // number

var emobilenumber = 9555356564;
console.log(typeof emobilenumber); // number

var esalary = 45000.99;
console.log(typeof esalary); // number

var ename = "mahesh";
console.log(typeof ename); // string

console.log(typeof "contract employee"); // string

var pf;
console.log(typeof pf); // undefined

var esi = null;
console.log(typeof esi); // object (JavaScript bug)

var desg = ["developer", "hr", "manager"];
console.log(typeof desg); // object

var customer_info = {
  cid: 2001,
  c_name: "rahul",
  c_add: "guntur",
};
console.log(typeof customer_info); // object

// advanced datatypes
var tcs_turnover = BigInt(65732673269872358763832n);
console.log(typeof tcs_turnover); // bigint

var p_name = Symbol("samsung");
var p_name1 = Symbol("samsung");

console.log(typeof p_name); // symbol
console.log(p_name == p_name1); // false
