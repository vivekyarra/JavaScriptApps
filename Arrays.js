//Arrays in js
// create a list of arrays
let listOfArrays = [
    [1, 2, 3],
    ["apple", "banana", "mango"],
    [true, false, true]
];

// print the entire list
console.log(listOfArrays);

// access individual arrays
console.log(listOfArrays[0]); // first array
console.log(listOfArrays[1]); // second array

// access specific elements
console.log(listOfArrays[1][0]); // apple

// add a new array to the list
listOfArrays.push([100, 200, 300]);

console.log(listOfArrays);
//arrays in js
//ways to create array
let p_names = ["apple","samsung","oneplus"];//literal synntax
let prices = new Array(100000, 69696, 50000);
//to get array values
console.log(p_names[1]);
for(let names of p_names)
{
    console.log(names);
}
//using foris method
let names = p_names.forEach(
    (val) =>{
        console.log(val);
    }
)
//to add elements
//push meathod,unshift method,splice method
p_names.push("blackberry");
for (let names of p_names);
{
    console.log(names);
}
p_names.unshift("nokia");
for (let names of p_names)
{
    console.log(names);
}
p_names.splice(2,0,"vivo","xiaomi");
for (let names of p_names)
{
    console.log(names);
}
//to remove elements
//pop method,shift method,splice method,delete operator
p_names.pop;
for (let names of p_names)
{
    console.log(names);
}
for (let names of p_names)
{
    console.log(names);
}
delete p_names [3];
for (let names of p_names)
{
  console.log(names);
}
//slice method
console.log(p_names.slice(2,4));
console.log(p_names.slice(-4,-2));
//to search
//index of last index of, includes,find are the methods
console.log(p_names.indexOf("samsung"));
//sort
//sort method
console.log(p_names.sort());
console.log(p_names.reverse());
//array advanced methods(ES6)
//reduce
let sum = prices.reduce((total , value)=>{
    return total+value;

});
console.log(sum);
//map
let offerPrice = prices.map((value) =>{
    return value-5000;
})
console.log(offerPrice);
//to concat
let p_names1 =["moto","poco"];
console.log(p_names.concat(p_names1));
//spread operator
let brands = [...p_names,...p_names1];

