//This keyword
const empInfo = {
    
    eFirstName:"vivek",
    eLastName:"yarra",
    FullName: function() {
        return this.eFirstName +" "+ this.eLastName;

    }
};
console.log(empInfo.FullName());