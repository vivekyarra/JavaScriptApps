//functionns in js
function showMessage(){
    console.log("hi");
}
showMessage();
//function with parameters
function sumOfNumbers(a,b){
    console.log(a+b);
}
sumOfNumbers(10,20);
//return a value from function
function mulOfNumbers(a,b){
    return a*b;
}
let x = mulOfNumbers(10,20);
console.log(x);
//Es6 new functions(arow function)
const arrowDemo = () => {
    console.log("arrow function demo");
}
arrowDemo();
//arrow functions with parameters
const addNumbers = (num1,num2)=> {
    console.log(num1+num2);
}
addNumbers(20,30);
//arrow functions in simple way
const addNums1 = (num1,num2) => num1+num2;
let ans=addNums1(10,20);
console.log(ans);
//print two numbers using arrow .rest parameters
const printValues = (a, b,...c) => {
  console.log("First value:", a);
  console.log("Second value:",b);
  console.log("remaining values:",...c);
};
// function call
printValues(10, 20, 30,40,50);
//default parameters
const sumNummbers = (a,b=20) =>
{
    console.log(a+b);
}
sumNummbers(10,40);
