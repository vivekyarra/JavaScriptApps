//call method
const pInfo ={
    pId: 1001,

    pName:"apple",
    pDetails: function(rating,price) {
        return this.pId +" "+ this.pName + " " + rating + " " + price;
    },
};
const product = {
    pId: 1001,
    pName: "apple",
};
console.log(pInfo.pDetails.call(product,4.5,100000));