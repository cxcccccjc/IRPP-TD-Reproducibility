package rq5.contracts;

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.fisco.bcos.sdk.v3.client.Client;
import org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes;
import org.fisco.bcos.sdk.v3.codec.datatypes.Event;
import org.fisco.bcos.sdk.v3.codec.datatypes.Function;
import org.fisco.bcos.sdk.v3.codec.datatypes.Type;
import org.fisco.bcos.sdk.v3.codec.datatypes.TypeReference;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint256;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint32;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint8;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.tuples.generated.Tuple2;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.tuples.generated.Tuple3;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.tuples.generated.Tuple4;
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.tuples.generated.Tuple8;
import org.fisco.bcos.sdk.v3.contract.Contract;
import org.fisco.bcos.sdk.v3.crypto.CryptoSuite;
import org.fisco.bcos.sdk.v3.crypto.keypair.CryptoKeyPair;
import org.fisco.bcos.sdk.v3.eventsub.EventSubCallback;
import org.fisco.bcos.sdk.v3.model.CryptoType;
import org.fisco.bcos.sdk.v3.model.TransactionReceipt;
import org.fisco.bcos.sdk.v3.model.callback.CallCallback;
import org.fisco.bcos.sdk.v3.model.callback.TransactionCallback;
import org.fisco.bcos.sdk.v3.transaction.model.exception.ContractException;

@SuppressWarnings("unchecked")
public class RPPSWorkflow extends Contract {
    public static final String[] BINARY_ARRAY = {"608060405234801561001057600080fd5b50610b70806100206000396000f3fe608060405234801561001057600080fd5b50600436106100a95760003560e01c80638f8c0b4e116100715780638f8c0b4e146100ae578063d32a9cd91461014d578063dc2af29b14610160578063deb2693114610173578063e579f50014610186578063e998f09d146101ad57600080fd5b8063147d145f146100ae5780632b11cab5146100ee57806341d9885c146101015780634f77d86c146101145780636902ebee14610127575b600080fd5b6100ec6100bc366004610894565b600091825260026020526040909120805467ffffffffffffffff191667ffffffffffffffff909216919091179055565b005b6100ec6100fc3660046108d1565b6101f0565b6100ec61010f36600461093c565b6102e0565b6100ec6101223660046108d1565b6103b9565b61013a6101353660046108d1565b610456565b6040519081526020015b60405180910390f35b6100ec61015b3660046108d1565b610482565b6100ec61016e3660046108d1565b610516565b6100ec6101813660046109b0565b6105b4565b610199610194366004610a03565b61071f565b604051610144989796959493929190610a1c565b6101d76101bb366004610a03565b60026020526000908152604090205467ffffffffffffffff1681565b60405167ffffffffffffffff9091168152602001610144565b6000828152602081905260409020600681015460ff166001146102485760405162461bcd60e51b815260206004820152600b60248201526a77726f6e6720737461746560a81b60448201526064015b60405180910390fd5b6002810154640100000000810463ffffffff90811691161461029e5760405162461bcd60e51b815260206004820152600f60248201526e6d697373696e67207265706f72747360881b604482015260640161023f565b6003810182905560405182815283907f71cf5091309af0300e5043f6e044a15bd8b6ea2cdecb53e46e6353ddb2b4ba29906020015b60405180910390a2505050565b60008581526020819052604090206006015460ff16156103305760405162461bcd60e51b815260206004820152600b60248201526a7461736b2065786973747360a81b604482015260640161023f565b60008581526020819052604090206103498186866107fb565b50600181810184905560028201805463ffffffff191663ffffffff851690811790915560068301805460ff191690921790915560405190815286907fc05a1debbf48c2c0d31cc97bdf0621e6d3b4d939ef4f284600d0d205bd1699199060200160405180910390a2505050505050565b6000828152602081905260409020600681015460ff1660011461040c5760405162461bcd60e51b815260206004820152600b60248201526a77726f6e6720737461746560a81b604482015260640161023f565b6004810182905560068101805460ff1916600217905560405183907f2d098a317e02c66d3edf12bd8430eecbeaf820a7daaa0e7be3364c99c132fc29906102d39085815260200190565b60008281526001602090815260408083208484529091528120805461047a90610ac9565b949350505050565b6000828152602081905260409020600681015460ff166003146104d35760405162461bcd60e51b81526020600482015260096024820152681b9bc81c995cdd5b1d60ba1b604482015260640161023f565b60068101805460ff1916600417905560405183907f170651f316bde520e85f746dca889e6e682e61f5fb18b86705e17a10b127ad07906102d39085815260200190565b6000828152602081905260409020600681015460ff1660021461056a5760405162461bcd60e51b815260206004820152600c60248201526b1b9bdd081cd95b1958dd195960a21b604482015260640161023f565b6005810182905560068101805460ff1916600317905560405183907fab14c33f77a05fafeba93466c450d59bfd30d642915aede2e49136cb3f966c39906102d39085815260200190565b6000848152602081905260409020600681015460ff1660011461060a5760405162461bcd60e51b815260206004820152600e60248201526d6e6f7420636f6c6c656374696e6760901b604482015260640161023f565b60008581526001602090815260408083208784529091529020805461062e90610ac9565b1590506106695760405162461bcd60e51b81526020600482015260096024820152686475706c696361746560b81b604482015260640161023f565b6000858152600160209081526040808320878452909152902061068d9084846107fb565b5060018160020160048282829054906101000a900463ffffffff166106b29190610b04565b92506101000a81548163ffffffff021916908363ffffffff16021790555083857f93731d66ca4eaf3adf2bb96a0a6baab203e35cf7a11536f4eec82c8af249593185859050604051610710919063ffffffff91909116815260200190565b60405180910390a35050505050565b60006020819052908152604090208054819061073a90610ac9565b80601f016020809104026020016040519081016040528092919081815260200182805461076690610ac9565b80156107b35780601f10610788576101008083540402835291602001916107b3565b820191906000526020600020905b81548152906001019060200180831161079657829003601f168201915b505050600184015460028501546003860154600487015460058801546006909801549697939663ffffffff808516975064010000000090940490931694509092909160ff1688565b82805461080790610ac9565b90600052602060002090601f016020900481019282610829576000855561086f565b82601f106108425782800160ff1982351617855561086f565b8280016001018555821561086f579182015b8281111561086f578235825591602001919060010190610854565b5061087b92915061087f565b5090565b5b8082111561087b5760008155600101610880565b600080604083850312156108a757600080fd5b82359150602083013567ffffffffffffffff811681146108c657600080fd5b809150509250929050565b600080604083850312156108e457600080fd5b50508035926020909101359150565b60008083601f84011261090557600080fd5b50813567ffffffffffffffff81111561091d57600080fd5b60208301915083602082850101111561093557600080fd5b9250929050565b60008060008060006080868803121561095457600080fd5b85359450602086013567ffffffffffffffff81111561097257600080fd5b61097e888289016108f3565b90955093505060408601359150606086013563ffffffff811681146109a257600080fd5b809150509295509295909350565b600080600080606085870312156109c657600080fd5b8435935060208501359250604085013567ffffffffffffffff8111156109eb57600080fd5b6109f7878288016108f3565b95989497509550505050565b600060208284031215610a1557600080fd5b5035919050565b60006101008083528a518082850152600091505b80821015610a52576020828d0101516101208386010152602082019150610a30565b80821115610a6557600061012082860101525b602084018b9052601f01601f19168301610120019150610a8f9050604083018963ffffffff169052565b63ffffffff871660608301528560808301528460a08301528360c0830152610abc60e083018460ff169052565b9998505050505050505050565b600181811c90821680610add57607f821691505b60208210811415610afe57634e487b7160e01b600052602260045260246000fd5b50919050565b600063ffffffff808316818516808303821115610b3157634e487b7160e01b600052601160045260246000fd5b0194935050505056fea2646970667358221220ac3e7610d2e17ee6ea40f3387e1609232cb97e177050b41ba19461896a69a27e64736f6c634300080b0033"};

    public static final String BINARY = org.fisco.bcos.sdk.v3.utils.StringUtils.joinAll("", BINARY_ARRAY);

    public static final String[] SM_BINARY_ARRAY = {"608060405234801561001057600080fd5b50610b7c806100206000396000f3fe608060405234801561001057600080fd5b50600436106100a95760003560e01c806359cda3fe1161007157806359cda3fe146100e95780636a392e671461014d578063acdd42fe14610160578063ae823af0146101a3578063b5a8c620146101ca578063c78ec556146101dd57600080fd5b8063052eabc7146100ae5780630f390165146100c35780631ea2a7bd146100d657806321a08ab0146100e957806328bd05d314610127575b600080fd5b6100c16100bc3660046108a0565b6101f0565b005b6100c16100d13660046108a0565b6102a0565b6100c16100e436600461090b565b610335565b6100c16100f736600461095e565b600091825260026020526040909120805467ffffffffffffffff191667ffffffffffffffff909216919091179055565b61013a6101353660046108a0565b6104a2565b6040519081526020015b60405180910390f35b6100c161015b36600461099b565b6104ce565b61018a61016e366004610a0f565b60026020526000908152604090205467ffffffffffffffff1681565b60405167ffffffffffffffff9091168152602001610144565b6101b66101b1366004610a0f565b6105a8565b604051610144989796959493929190610a28565b6100c16101d83660046108a0565b610684565b6100c16101eb3660046108a0565b610768565b6000828152602081905260409020600681015460ff1660011461024957604051636381e58960e11b815260206004820152600b60248201526a77726f6e6720737461746560a81b60448201526064015b60405180910390fd5b6004810182905560068101805460ff1916600217905560405183907ff734ef0559a97674f5afd31f5ae14183a77d6856a74d4ddb0452f0551f93ad99906102939085815260200190565b60405180910390a2505050565b6000828152602081905260409020600681015460ff166003146102f257604051636381e58960e11b81526020600482015260096024820152681b9bc81c995cdd5b1d60ba1b6044820152606401610240565b60068101805460ff1916600417905560405183907fb816b03590cb6dacd4b7e3c5e38d67b0e91dbf51bba9d292575642d6b1dba4d1906102939085815260200190565b6000848152602081905260409020600681015460ff1660011461038c57604051636381e58960e11b815260206004820152600e60248201526d6e6f7420636f6c6c656374696e6760901b6044820152606401610240565b6000858152600160209081526040808320878452909152902080546103b090610ad5565b1590506103ec57604051636381e58960e11b81526020600482015260096024820152686475706c696361746560b81b6044820152606401610240565b60008581526001602090815260408083208784529091529020610410908484610807565b5060018160020160048282829054906101000a900463ffffffff166104359190610b10565b92506101000a81548163ffffffff021916908363ffffffff16021790555083857f4af005f4efd657f18c207343c29c834ccf97b269db913948e0e8f1d30dbfa16585859050604051610493919063ffffffff91909116815260200190565b60405180910390a35050505050565b6000828152600160209081526040808320848452909152812080546104c690610ad5565b949350505050565b60008581526020819052604090206006015460ff161561051f57604051636381e58960e11b815260206004820152600b60248201526a7461736b2065786973747360a81b6044820152606401610240565b6000858152602081905260409020610538818686610807565b50600181810184905560028201805463ffffffff191663ffffffff851690811790915560068301805460ff191690921790915560405190815286907f5f8eabd610c77620b81106b37d4332c2df48e0a38c28a45d99c974b6cbb2bf509060200160405180910390a2505050505050565b6000602081905290815260409020805481906105c390610ad5565b80601f01602080910402602001604051908101604052809291908181526020018280546105ef90610ad5565b801561063c5780601f106106115761010080835404028352916020019161063c565b820191906000526020600020905b81548152906001019060200180831161061f57829003601f168201915b505050600184015460028501546003860154600487015460058801546006909801549697939663ffffffff808516975064010000000090940490931694509092909160ff1688565b6000828152602081905260409020600681015460ff166001146106d857604051636381e58960e11b815260206004820152600b60248201526a77726f6e6720737461746560a81b6044820152606401610240565b6002810154640100000000810463ffffffff90811691161461072f57604051636381e58960e11b815260206004820152600f60248201526e6d697373696e67207265706f72747360881b6044820152606401610240565b6003810182905560405182815283907fda1f1258be81df42181cf189af59372afa162f27cb646f0e14641a704477103890602001610293565b6000828152602081905260409020600681015460ff166002146107bd57604051636381e58960e11b815260206004820152600c60248201526b1b9bdd081cd95b1958dd195960a21b6044820152606401610240565b6005810182905560068101805460ff1916600317905560405183907f0ca7984368dfb42710d8a869af222b01cd71278befbc47dd0a886f0dbcc7d68e906102939085815260200190565b82805461081390610ad5565b90600052602060002090601f016020900481019282610835576000855561087b565b82601f1061084e5782800160ff1982351617855561087b565b8280016001018555821561087b579182015b8281111561087b578235825591602001919060010190610860565b5061088792915061088b565b5090565b5b80821115610887576000815560010161088c565b600080604083850312156108b357600080fd5b50508035926020909101359150565b60008083601f8401126108d457600080fd5b50813567ffffffffffffffff8111156108ec57600080fd5b60208301915083602082850101111561090457600080fd5b9250929050565b6000806000806060858703121561092157600080fd5b8435935060208501359250604085013567ffffffffffffffff81111561094657600080fd5b610952878288016108c2565b95989497509550505050565b6000806040838503121561097157600080fd5b82359150602083013567ffffffffffffffff8116811461099057600080fd5b809150509250929050565b6000806000806000608086880312156109b357600080fd5b85359450602086013567ffffffffffffffff8111156109d157600080fd5b6109dd888289016108c2565b90955093505060408601359150606086013563ffffffff81168114610a0157600080fd5b809150509295509295909350565b600060208284031215610a2157600080fd5b5035919050565b60006101008083528a518082850152600091505b80821015610a5e576020828d0101516101208386010152602082019150610a3c565b80821115610a7157600061012082860101525b602084018b9052601f01601f19168301610120019150610a9b9050604083018963ffffffff169052565b63ffffffff871660608301528560808301528460a08301528360c0830152610ac860e083018460ff169052565b9998505050505050505050565b600181811c90821680610ae957607f821691505b60208210811415610b0a5763b95aa35560e01b600052602260045260246000fd5b50919050565b600063ffffffff808316818516808303821115610b3d5763b95aa35560e01b600052601160045260246000fd5b0194935050505056fea264697066735822122065f49c7d4b73fbcfdd058c3bf6f0e455845a70693cd119892a7d07a99679740e64736f6c634300080b0033"};

    public static final String SM_BINARY = org.fisco.bcos.sdk.v3.utils.StringUtils.joinAll("", SM_BINARY_ARRAY);

    public static final String[] ABI_ARRAY = {"[{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"uint32\",\"name\":\"bytesLength\",\"type\":\"uint32\"}],\"name\":\"ReportUploaded\",\"type\":\"event\"},{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"bytes32\",\"name\":\"resultRoot\",\"type\":\"bytes32\"}],\"name\":\"ResultCommitted\",\"type\":\"event\"},{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"bytes32\",\"name\":\"selectionRoot\",\"type\":\"bytes32\"}],\"name\":\"SelectionCommitted\",\"type\":\"event\"},{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"bytes32\",\"name\":\"paymentRoot\",\"type\":\"bytes32\"}],\"name\":\"Settled\",\"type\":\"event\"},{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"uint32\",\"name\":\"expectedWorkers\",\"type\":\"uint32\"}],\"name\":\"TaskPublished\",\"type\":\"event\"},{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"bytes32\",\"name\":\"trustRoot\",\"type\":\"bytes32\"}],\"name\":\"TrustCommitted\",\"type\":\"event\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"resultRoot\",\"type\":\"bytes32\"}],\"name\":\"commitResult\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"selectionRoot\",\"type\":\"bytes32\"}],\"name\":\"commitSelection\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"trustRoot\",\"type\":\"bytes32\"}],\"name\":\"commitTrust\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes\",\"name\":\"encryptedTask\",\"type\":\"bytes\"},{\"internalType\":\"bytes32\",\"name\":\"geohashTag\",\"type\":\"bytes32\"},{\"internalType\":\"uint32\",\"name\":\"expectedWorkers\",\"type\":\"uint32\"}],\"name\":\"publishTask\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"},{\"internalType\":\"uint64\",\"name\":\"initialReputation\",\"type\":\"uint64\"}],\"name\":\"registerWorker\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"}],\"name\":\"reportLength\",\"outputs\":[{\"internalType\":\"uint256\",\"name\":\"\",\"type\":\"uint256\"}],\"stateMutability\":\"view\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"\",\"type\":\"bytes32\"}],\"name\":\"reputation\",\"outputs\":[{\"internalType\":\"uint64\",\"name\":\"\",\"type\":\"uint64\"}],\"stateMutability\":\"view\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"paymentRoot\",\"type\":\"bytes32\"}],\"name\":\"settle\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"\",\"type\":\"bytes32\"}],\"name\":\"tasks\",\"outputs\":[{\"internalType\":\"bytes\",\"name\":\"encryptedTask\",\"type\":\"bytes\"},{\"internalType\":\"bytes32\",\"name\":\"geohashTag\",\"type\":\"bytes32\"},{\"internalType\":\"uint32\",\"name\":\"expectedWorkers\",\"type\":\"uint32\"},{\"internalType\":\"uint32\",\"name\":\"reports\",\"type\":\"uint32\"},{\"internalType\":\"bytes32\",\"name\":\"trustRoot\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"selectionRoot\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"resultRoot\",\"type\":\"bytes32\"},{\"internalType\":\"uint8\",\"name\":\"state\",\"type\":\"uint8\"}],\"stateMutability\":\"view\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"},{\"internalType\":\"uint64\",\"name\":\"nextReputation\",\"type\":\"uint64\"}],\"name\":\"updateReputation\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"},{\"internalType\":\"bytes\",\"name\":\"ciphertext\",\"type\":\"bytes\"}],\"name\":\"uploadReport\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"}]"};

    public static final String ABI = org.fisco.bcos.sdk.v3.utils.StringUtils.joinAll("", ABI_ARRAY);

    public static final String FUNC_COMMITRESULT = "commitResult";

    public static final String FUNC_COMMITSELECTION = "commitSelection";

    public static final String FUNC_COMMITTRUST = "commitTrust";

    public static final String FUNC_PUBLISHTASK = "publishTask";

    public static final String FUNC_REGISTERWORKER = "registerWorker";

    public static final String FUNC_REPORTLENGTH = "reportLength";

    public static final String FUNC_REPUTATION = "reputation";

    public static final String FUNC_SETTLE = "settle";

    public static final String FUNC_TASKS = "tasks";

    public static final String FUNC_UPDATEREPUTATION = "updateReputation";

    public static final String FUNC_UPLOADREPORT = "uploadReport";

    public static final Event REPORTUPLOADED_EVENT = new Event("ReportUploaded", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Bytes32>(true) {}, new TypeReference<Uint32>() {}));
    ;

    public static final Event RESULTCOMMITTED_EVENT = new Event("ResultCommitted", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Bytes32>() {}));
    ;

    public static final Event SELECTIONCOMMITTED_EVENT = new Event("SelectionCommitted", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Bytes32>() {}));
    ;

    public static final Event SETTLED_EVENT = new Event("Settled", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Bytes32>() {}));
    ;

    public static final Event TASKPUBLISHED_EVENT = new Event("TaskPublished", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Uint32>() {}));
    ;

    public static final Event TRUSTCOMMITTED_EVENT = new Event("TrustCommitted", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Bytes32>() {}));
    ;

    protected RPPSWorkflow(String contractAddress, Client client, CryptoKeyPair credential) {
        super(getBinary(client.getCryptoSuite()), contractAddress, client, credential);
    }

    public static String getBinary(CryptoSuite cryptoSuite) {
        return (cryptoSuite.getCryptoTypeConfig() == CryptoType.ECDSA_TYPE ? BINARY : SM_BINARY);
    }

    public static String getABI() {
        return ABI;
    }

    public List<ReportUploadedEventResponse> getReportUploadedEvents(
            TransactionReceipt transactionReceipt) {
        List<Contract.EventValuesWithLog> valueList = extractEventParametersWithLog(REPORTUPLOADED_EVENT, transactionReceipt);
        ArrayList<ReportUploadedEventResponse> responses = new ArrayList<ReportUploadedEventResponse>(valueList.size());
        for (Contract.EventValuesWithLog eventValues : valueList) {
            ReportUploadedEventResponse typedResponse = new ReportUploadedEventResponse();
            typedResponse.log = eventValues.getLog();
            typedResponse.taskId = (byte[]) eventValues.getIndexedValues().get(0).getValue();
            typedResponse.workerTag = (byte[]) eventValues.getIndexedValues().get(1).getValue();
            typedResponse.bytesLength = (BigInteger) eventValues.getNonIndexedValues().get(0).getValue();
            responses.add(typedResponse);
        }
        return responses;
    }

    public void subscribeReportUploadedEvent(BigInteger fromBlock, BigInteger toBlock,
            List<String> otherTopics, EventSubCallback callback) {
        String topic0 = eventEncoder.encode(REPORTUPLOADED_EVENT);
        subscribeEvent(topic0,otherTopics,fromBlock,toBlock,callback);
    }

    public void subscribeReportUploadedEvent(EventSubCallback callback) {
        String topic0 = eventEncoder.encode(REPORTUPLOADED_EVENT);
        subscribeEvent(topic0,callback);
    }

    public List<ResultCommittedEventResponse> getResultCommittedEvents(
            TransactionReceipt transactionReceipt) {
        List<Contract.EventValuesWithLog> valueList = extractEventParametersWithLog(RESULTCOMMITTED_EVENT, transactionReceipt);
        ArrayList<ResultCommittedEventResponse> responses = new ArrayList<ResultCommittedEventResponse>(valueList.size());
        for (Contract.EventValuesWithLog eventValues : valueList) {
            ResultCommittedEventResponse typedResponse = new ResultCommittedEventResponse();
            typedResponse.log = eventValues.getLog();
            typedResponse.taskId = (byte[]) eventValues.getIndexedValues().get(0).getValue();
            typedResponse.resultRoot = (byte[]) eventValues.getNonIndexedValues().get(0).getValue();
            responses.add(typedResponse);
        }
        return responses;
    }

    public void subscribeResultCommittedEvent(BigInteger fromBlock, BigInteger toBlock,
            List<String> otherTopics, EventSubCallback callback) {
        String topic0 = eventEncoder.encode(RESULTCOMMITTED_EVENT);
        subscribeEvent(topic0,otherTopics,fromBlock,toBlock,callback);
    }

    public void subscribeResultCommittedEvent(EventSubCallback callback) {
        String topic0 = eventEncoder.encode(RESULTCOMMITTED_EVENT);
        subscribeEvent(topic0,callback);
    }

    public List<SelectionCommittedEventResponse> getSelectionCommittedEvents(
            TransactionReceipt transactionReceipt) {
        List<Contract.EventValuesWithLog> valueList = extractEventParametersWithLog(SELECTIONCOMMITTED_EVENT, transactionReceipt);
        ArrayList<SelectionCommittedEventResponse> responses = new ArrayList<SelectionCommittedEventResponse>(valueList.size());
        for (Contract.EventValuesWithLog eventValues : valueList) {
            SelectionCommittedEventResponse typedResponse = new SelectionCommittedEventResponse();
            typedResponse.log = eventValues.getLog();
            typedResponse.taskId = (byte[]) eventValues.getIndexedValues().get(0).getValue();
            typedResponse.selectionRoot = (byte[]) eventValues.getNonIndexedValues().get(0).getValue();
            responses.add(typedResponse);
        }
        return responses;
    }

    public void subscribeSelectionCommittedEvent(BigInteger fromBlock, BigInteger toBlock,
            List<String> otherTopics, EventSubCallback callback) {
        String topic0 = eventEncoder.encode(SELECTIONCOMMITTED_EVENT);
        subscribeEvent(topic0,otherTopics,fromBlock,toBlock,callback);
    }

    public void subscribeSelectionCommittedEvent(EventSubCallback callback) {
        String topic0 = eventEncoder.encode(SELECTIONCOMMITTED_EVENT);
        subscribeEvent(topic0,callback);
    }

    public List<SettledEventResponse> getSettledEvents(TransactionReceipt transactionReceipt) {
        List<Contract.EventValuesWithLog> valueList = extractEventParametersWithLog(SETTLED_EVENT, transactionReceipt);
        ArrayList<SettledEventResponse> responses = new ArrayList<SettledEventResponse>(valueList.size());
        for (Contract.EventValuesWithLog eventValues : valueList) {
            SettledEventResponse typedResponse = new SettledEventResponse();
            typedResponse.log = eventValues.getLog();
            typedResponse.taskId = (byte[]) eventValues.getIndexedValues().get(0).getValue();
            typedResponse.paymentRoot = (byte[]) eventValues.getNonIndexedValues().get(0).getValue();
            responses.add(typedResponse);
        }
        return responses;
    }

    public void subscribeSettledEvent(BigInteger fromBlock, BigInteger toBlock,
            List<String> otherTopics, EventSubCallback callback) {
        String topic0 = eventEncoder.encode(SETTLED_EVENT);
        subscribeEvent(topic0,otherTopics,fromBlock,toBlock,callback);
    }

    public void subscribeSettledEvent(EventSubCallback callback) {
        String topic0 = eventEncoder.encode(SETTLED_EVENT);
        subscribeEvent(topic0,callback);
    }

    public List<TaskPublishedEventResponse> getTaskPublishedEvents(
            TransactionReceipt transactionReceipt) {
        List<Contract.EventValuesWithLog> valueList = extractEventParametersWithLog(TASKPUBLISHED_EVENT, transactionReceipt);
        ArrayList<TaskPublishedEventResponse> responses = new ArrayList<TaskPublishedEventResponse>(valueList.size());
        for (Contract.EventValuesWithLog eventValues : valueList) {
            TaskPublishedEventResponse typedResponse = new TaskPublishedEventResponse();
            typedResponse.log = eventValues.getLog();
            typedResponse.taskId = (byte[]) eventValues.getIndexedValues().get(0).getValue();
            typedResponse.expectedWorkers = (BigInteger) eventValues.getNonIndexedValues().get(0).getValue();
            responses.add(typedResponse);
        }
        return responses;
    }

    public void subscribeTaskPublishedEvent(BigInteger fromBlock, BigInteger toBlock,
            List<String> otherTopics, EventSubCallback callback) {
        String topic0 = eventEncoder.encode(TASKPUBLISHED_EVENT);
        subscribeEvent(topic0,otherTopics,fromBlock,toBlock,callback);
    }

    public void subscribeTaskPublishedEvent(EventSubCallback callback) {
        String topic0 = eventEncoder.encode(TASKPUBLISHED_EVENT);
        subscribeEvent(topic0,callback);
    }

    public List<TrustCommittedEventResponse> getTrustCommittedEvents(
            TransactionReceipt transactionReceipt) {
        List<Contract.EventValuesWithLog> valueList = extractEventParametersWithLog(TRUSTCOMMITTED_EVENT, transactionReceipt);
        ArrayList<TrustCommittedEventResponse> responses = new ArrayList<TrustCommittedEventResponse>(valueList.size());
        for (Contract.EventValuesWithLog eventValues : valueList) {
            TrustCommittedEventResponse typedResponse = new TrustCommittedEventResponse();
            typedResponse.log = eventValues.getLog();
            typedResponse.taskId = (byte[]) eventValues.getIndexedValues().get(0).getValue();
            typedResponse.trustRoot = (byte[]) eventValues.getNonIndexedValues().get(0).getValue();
            responses.add(typedResponse);
        }
        return responses;
    }

    public void subscribeTrustCommittedEvent(BigInteger fromBlock, BigInteger toBlock,
            List<String> otherTopics, EventSubCallback callback) {
        String topic0 = eventEncoder.encode(TRUSTCOMMITTED_EVENT);
        subscribeEvent(topic0,otherTopics,fromBlock,toBlock,callback);
    }

    public void subscribeTrustCommittedEvent(EventSubCallback callback) {
        String topic0 = eventEncoder.encode(TRUSTCOMMITTED_EVENT);
        subscribeEvent(topic0,callback);
    }

    public TransactionReceipt commitResult(byte[] taskId, byte[] resultRoot) {
        final Function function = new Function(
                FUNC_COMMITRESULT, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(resultRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodCommitResultRawFunction(byte[] taskId, byte[] resultRoot) throws
            ContractException {
        final Function function = new Function(FUNC_COMMITRESULT, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(resultRoot)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForCommitResult(byte[] taskId, byte[] resultRoot) {
        final Function function = new Function(
                FUNC_COMMITRESULT, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(resultRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String commitResult(byte[] taskId, byte[] resultRoot, TransactionCallback callback) {
        final Function function = new Function(
                FUNC_COMMITRESULT, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(resultRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple2<byte[], byte[]> getCommitResultInput(TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_COMMITRESULT, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple2<byte[], byte[]>(

                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue()
                );
    }

    public TransactionReceipt commitSelection(byte[] taskId, byte[] selectionRoot) {
        final Function function = new Function(
                FUNC_COMMITSELECTION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(selectionRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodCommitSelectionRawFunction(byte[] taskId, byte[] selectionRoot) throws
            ContractException {
        final Function function = new Function(FUNC_COMMITSELECTION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(selectionRoot)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForCommitSelection(byte[] taskId, byte[] selectionRoot) {
        final Function function = new Function(
                FUNC_COMMITSELECTION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(selectionRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String commitSelection(byte[] taskId, byte[] selectionRoot,
            TransactionCallback callback) {
        final Function function = new Function(
                FUNC_COMMITSELECTION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(selectionRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple2<byte[], byte[]> getCommitSelectionInput(TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_COMMITSELECTION, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple2<byte[], byte[]>(

                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue()
                );
    }

    public TransactionReceipt commitTrust(byte[] taskId, byte[] trustRoot) {
        final Function function = new Function(
                FUNC_COMMITTRUST, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(trustRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodCommitTrustRawFunction(byte[] taskId, byte[] trustRoot) throws
            ContractException {
        final Function function = new Function(FUNC_COMMITTRUST, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(trustRoot)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForCommitTrust(byte[] taskId, byte[] trustRoot) {
        final Function function = new Function(
                FUNC_COMMITTRUST, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(trustRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String commitTrust(byte[] taskId, byte[] trustRoot, TransactionCallback callback) {
        final Function function = new Function(
                FUNC_COMMITTRUST, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(trustRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple2<byte[], byte[]> getCommitTrustInput(TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_COMMITTRUST, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple2<byte[], byte[]>(

                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue()
                );
    }

    public TransactionReceipt publishTask(byte[] taskId, byte[] encryptedTask, byte[] geohashTag,
            BigInteger expectedWorkers) {
        final Function function = new Function(
                FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(encryptedTask), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(geohashTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint32(expectedWorkers)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodPublishTaskRawFunction(byte[] taskId, byte[] encryptedTask,
            byte[] geohashTag, BigInteger expectedWorkers) throws ContractException {
        final Function function = new Function(FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(encryptedTask), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(geohashTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint32(expectedWorkers)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForPublishTask(byte[] taskId, byte[] encryptedTask,
            byte[] geohashTag, BigInteger expectedWorkers) {
        final Function function = new Function(
                FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(encryptedTask), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(geohashTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint32(expectedWorkers)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String publishTask(byte[] taskId, byte[] encryptedTask, byte[] geohashTag,
            BigInteger expectedWorkers, TransactionCallback callback) {
        final Function function = new Function(
                FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(encryptedTask), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(geohashTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint32(expectedWorkers)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple4<byte[], byte[], byte[], BigInteger> getPublishTaskInput(
            TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<DynamicBytes>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint32>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple4<byte[], byte[], byte[], BigInteger>(

                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue(), 
                (byte[]) results.get(2).getValue(), 
                (BigInteger) results.get(3).getValue()
                );
    }

    public TransactionReceipt registerWorker(byte[] workerTag, BigInteger initialReputation) {
        final Function function = new Function(
                FUNC_REGISTERWORKER, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64(initialReputation)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodRegisterWorkerRawFunction(byte[] workerTag,
            BigInteger initialReputation) throws ContractException {
        final Function function = new Function(FUNC_REGISTERWORKER, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64(initialReputation)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForRegisterWorker(byte[] workerTag,
            BigInteger initialReputation) {
        final Function function = new Function(
                FUNC_REGISTERWORKER, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64(initialReputation)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String registerWorker(byte[] workerTag, BigInteger initialReputation,
            TransactionCallback callback) {
        final Function function = new Function(
                FUNC_REGISTERWORKER, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64(initialReputation)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple2<byte[], BigInteger> getRegisterWorkerInput(
            TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_REGISTERWORKER, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<Uint64>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple2<byte[], BigInteger>(

                (byte[]) results.get(0).getValue(), 
                (BigInteger) results.get(1).getValue()
                );
    }

    public BigInteger reportLength(byte[] taskId, byte[] workerTag) throws ContractException {
        final Function function = new Function(FUNC_REPORTLENGTH, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Uint256>() {}));
        return executeCallWithSingleValueReturn(function, BigInteger.class);
    }

    public Function getMethodReportLengthRawFunction(byte[] taskId, byte[] workerTag) throws
            ContractException {
        final Function function = new Function(FUNC_REPORTLENGTH, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Uint256>() {}));
        return function;
    }

    public void reportLength(byte[] taskId, byte[] workerTag, CallCallback callback) throws
            ContractException {
        final Function function = new Function(FUNC_REPORTLENGTH, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Uint256>() {}));
        asyncExecuteCall(function, callback);
    }

    public BigInteger reputation(byte[] param0) throws ContractException {
        final Function function = new Function(FUNC_REPUTATION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Uint64>() {}));
        return executeCallWithSingleValueReturn(function, BigInteger.class);
    }

    public Function getMethodReputationRawFunction(byte[] param0) throws ContractException {
        final Function function = new Function(FUNC_REPUTATION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Uint64>() {}));
        return function;
    }

    public void reputation(byte[] param0, CallCallback callback) throws ContractException {
        final Function function = new Function(FUNC_REPUTATION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Uint64>() {}));
        asyncExecuteCall(function, callback);
    }

    public TransactionReceipt settle(byte[] taskId, byte[] paymentRoot) {
        final Function function = new Function(
                FUNC_SETTLE, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(paymentRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodSettleRawFunction(byte[] taskId, byte[] paymentRoot) throws
            ContractException {
        final Function function = new Function(FUNC_SETTLE, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(paymentRoot)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForSettle(byte[] taskId, byte[] paymentRoot) {
        final Function function = new Function(
                FUNC_SETTLE, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(paymentRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String settle(byte[] taskId, byte[] paymentRoot, TransactionCallback callback) {
        final Function function = new Function(
                FUNC_SETTLE, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(paymentRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple2<byte[], byte[]> getSettleInput(TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_SETTLE, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple2<byte[], byte[]>(

                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue()
                );
    }

    public Tuple8<byte[], byte[], BigInteger, BigInteger, byte[], byte[], byte[], BigInteger> tasks(
            byte[] param0) throws ContractException {
        final Function function = new Function(FUNC_TASKS, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<DynamicBytes>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint8>() {}));
        List<Type> results = executeCallWithMultipleValueReturn(function);
        return new Tuple8<byte[], byte[], BigInteger, BigInteger, byte[], byte[], byte[], BigInteger>(
                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue(), 
                (BigInteger) results.get(2).getValue(), 
                (BigInteger) results.get(3).getValue(), 
                (byte[]) results.get(4).getValue(), 
                (byte[]) results.get(5).getValue(), 
                (byte[]) results.get(6).getValue(), 
                (BigInteger) results.get(7).getValue());
    }

    public Function getMethodTasksRawFunction(byte[] param0) throws ContractException {
        final Function function = new Function(FUNC_TASKS, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<DynamicBytes>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint8>() {}));
        return function;
    }

    public void tasks(byte[] param0, CallCallback callback) throws ContractException {
        final Function function = new Function(FUNC_TASKS, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<DynamicBytes>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint8>() {}));
        asyncExecuteCall(function, callback);
    }

    public TransactionReceipt updateReputation(byte[] workerTag, BigInteger nextReputation) {
        final Function function = new Function(
                FUNC_UPDATEREPUTATION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64(nextReputation)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodUpdateReputationRawFunction(byte[] workerTag,
            BigInteger nextReputation) throws ContractException {
        final Function function = new Function(FUNC_UPDATEREPUTATION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64(nextReputation)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForUpdateReputation(byte[] workerTag,
            BigInteger nextReputation) {
        final Function function = new Function(
                FUNC_UPDATEREPUTATION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64(nextReputation)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String updateReputation(byte[] workerTag, BigInteger nextReputation,
            TransactionCallback callback) {
        final Function function = new Function(
                FUNC_UPDATEREPUTATION, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint64(nextReputation)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple2<byte[], BigInteger> getUpdateReputationInput(
            TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_UPDATEREPUTATION, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<Uint64>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple2<byte[], BigInteger>(

                (byte[]) results.get(0).getValue(), 
                (BigInteger) results.get(1).getValue()
                );
    }

    public TransactionReceipt uploadReport(byte[] taskId, byte[] workerTag, byte[] ciphertext) {
        final Function function = new Function(
                FUNC_UPLOADREPORT, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(ciphertext)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodUploadReportRawFunction(byte[] taskId, byte[] workerTag,
            byte[] ciphertext) throws ContractException {
        final Function function = new Function(FUNC_UPLOADREPORT, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(ciphertext)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForUploadReport(byte[] taskId, byte[] workerTag,
            byte[] ciphertext) {
        final Function function = new Function(
                FUNC_UPLOADREPORT, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(ciphertext)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String uploadReport(byte[] taskId, byte[] workerTag, byte[] ciphertext,
            TransactionCallback callback) {
        final Function function = new Function(
                FUNC_UPLOADREPORT, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(workerTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(ciphertext)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple3<byte[], byte[], byte[]> getUploadReportInput(
            TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_UPLOADREPORT, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<DynamicBytes>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple3<byte[], byte[], byte[]>(

                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue(), 
                (byte[]) results.get(2).getValue()
                );
    }

    public static RPPSWorkflow load(String contractAddress, Client client,
            CryptoKeyPair credential) {
        return new RPPSWorkflow(contractAddress, client, credential);
    }

    public static RPPSWorkflow deploy(Client client, CryptoKeyPair credential) throws
            ContractException {
        return deploy(RPPSWorkflow.class, client, credential, getBinary(client.getCryptoSuite()), getABI(), null, null);
    }

    public static class ReportUploadedEventResponse {
        public TransactionReceipt.Logs log;

        public byte[] taskId;

        public byte[] workerTag;

        public BigInteger bytesLength;
    }

    public static class ResultCommittedEventResponse {
        public TransactionReceipt.Logs log;

        public byte[] taskId;

        public byte[] resultRoot;
    }

    public static class SelectionCommittedEventResponse {
        public TransactionReceipt.Logs log;

        public byte[] taskId;

        public byte[] selectionRoot;
    }

    public static class SettledEventResponse {
        public TransactionReceipt.Logs log;

        public byte[] taskId;

        public byte[] paymentRoot;
    }

    public static class TaskPublishedEventResponse {
        public TransactionReceipt.Logs log;

        public byte[] taskId;

        public BigInteger expectedWorkers;
    }

    public static class TrustCommittedEventResponse {
        public TransactionReceipt.Logs log;

        public byte[] taskId;

        public byte[] trustRoot;
    }
}
