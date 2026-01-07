//loops in java script
// Program to print numbers from 1 to 10 using for loop
for (let i = 1; i <= 10; i++) {
    console.log(i);
}
// Program to print numbers from 1 to 10 using while loop
let i = 1;

while (i <= 10) {
    console.log(i);
    i++;
}
// Program to print numbers from 1 to 10 using do-while loop

let k = 1;

do {
    console.log(k);
    k++;
} while (k <= 10);
//new loops in es6
//for in & for of(used to retrive data from iterables(either string or object or arrays is iterables))
let pname = ["apple","samsung","oneplus","xiaomi"];
for (let names of pname) {
    console.log(names);
}

let pnames = ["apple", "samsung", "oneplus", "xiaomi"];
for (let names in pnames) {
  console.log(pnames[names]);
}
let empinfo = {
    ename:"vivek",
    esalary: 6969696,
};
for (let info in empinfo) {
    console.log(empinfo[info]);
}
//how to retrive from string
let collegename = "vlits";
for(let name in collegename) {
    console.log(name);
}