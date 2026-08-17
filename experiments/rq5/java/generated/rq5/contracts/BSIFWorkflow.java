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
import org.fisco.bcos.sdk.v3.codec.datatypes.generated.tuples.generated.Tuple6;
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
public class BSIFWorkflow extends Contract {
    public static final String[] BINARY_ARRAY = {"608060405234801561001057600080fd5b506109e9806100206000396000f3fe608060405234801561001057600080fd5b50600436106100935760003560e01c80638f8c0b4e116100665780638f8c0b4e14610098578063d32a9cd914610124578063deb2693114610137578063e579f5001461014a578063e998f09d1461016f57600080fd5b8063147d145f146100985780633134e255146100d857806341d9885c146100eb5780636902ebee146100fe575b600080fd5b6100d66100a6366004610726565b600091825260026020526040909120805467ffffffffffffffff191667ffffffffffffffff909216919091179055565b005b6100d66100e6366004610763565b6101b2565b6100d66100f93660046107ce565b6102b7565b61011161010c366004610763565b610390565b6040519081526020015b60405180910390f35b6100d6610132366004610763565b6103bc565b6100d6610145366004610842565b610454565b61015d610158366004610895565b6105bf565b60405161011b969594939291906108ae565b61019961017d366004610895565b60026020526000908152604090205467ffffffffffffffff1681565b60405167ffffffffffffffff909116815260200161011b565b6000828152602081905260409020600481015460ff1660011461020a5760405162461bcd60e51b815260206004820152600b60248201526a77726f6e6720737461746560a81b60448201526064015b60405180910390fd5b6002810154640100000000810463ffffffff9081169116146102605760405162461bcd60e51b815260206004820152600f60248201526e6d697373696e67207265706f72747360881b6044820152606401610201565b6003810182905560048101805460ff1916600217905560405183907f03817cd35aa4a0a7d42589790667a04705b977e35767ce5b62e2db311f997e99906102aa9085815260200190565b60405180910390a2505050565b60008581526020819052604090206004015460ff16156103075760405162461bcd60e51b815260206004820152600b60248201526a7461736b2065786973747360a81b6044820152606401610201565b600085815260208190526040902061032081868661068d565b50600181810184905560028201805463ffffffff191663ffffffff851690811790915560048301805460ff191690921790915560405190815286907fc05a1debbf48c2c0d31cc97bdf0621e6d3b4d939ef4f284600d0d205bd1699199060200160405180910390a2505050505050565b6000828152600160209081526040808320848452909152812080546103b490610942565b949350505050565b6000828152602081905260409020600481015460ff166002146104115760405162461bcd60e51b815260206004820152600d60248201526c1b9bdd08195d985b1d585d1959609a1b6044820152606401610201565b60048101805460ff1916600317905560405183907f170651f316bde520e85f746dca889e6e682e61f5fb18b86705e17a10b127ad07906102aa9085815260200190565b6000848152602081905260409020600481015460ff166001146104aa5760405162461bcd60e51b815260206004820152600e60248201526d6e6f7420636f6c6c656374696e6760901b6044820152606401610201565b6000858152600160209081526040808320878452909152902080546104ce90610942565b1590506105095760405162461bcd60e51b81526020600482015260096024820152686475706c696361746560b81b6044820152606401610201565b6000858152600160209081526040808320878452909152902061052d90848461068d565b5060018160020160048282829054906101000a900463ffffffff16610552919061097d565b92506101000a81548163ffffffff021916908363ffffffff16021790555083857f93731d66ca4eaf3adf2bb96a0a6baab203e35cf7a11536f4eec82c8af2495931858590506040516105b0919063ffffffff91909116815260200190565b60405180910390a35050505050565b6000602081905290815260409020805481906105da90610942565b80601f016020809104026020016040519081016040528092919081815260200182805461060690610942565b80156106535780601f1061062857610100808354040283529160200191610653565b820191906000526020600020905b81548152906001019060200180831161063657829003601f168201915b5050506001840154600285015460038601546004909601549495919463ffffffff8083169550640100000000909204909116925060ff1686565b82805461069990610942565b90600052602060002090601f0160209004810192826106bb5760008555610701565b82601f106106d45782800160ff19823516178555610701565b82800160010185558215610701579182015b828111156107015782358255916020019190600101906106e6565b5061070d929150610711565b5090565b5b8082111561070d5760008155600101610712565b6000806040838503121561073957600080fd5b82359150602083013567ffffffffffffffff8116811461075857600080fd5b809150509250929050565b6000806040838503121561077657600080fd5b50508035926020909101359150565b60008083601f84011261079757600080fd5b50813567ffffffffffffffff8111156107af57600080fd5b6020830191508360208285010111156107c757600080fd5b9250929050565b6000806000806000608086880312156107e657600080fd5b85359450602086013567ffffffffffffffff81111561080457600080fd5b61081088828901610785565b90955093505060408601359150606086013563ffffffff8116811461083457600080fd5b809150509295509295909350565b6000806000806060858703121561085857600080fd5b8435935060208501359250604085013567ffffffffffffffff81111561087d57600080fd5b61088987828801610785565b95989497509550505050565b6000602082840312156108a757600080fd5b5035919050565b60c08152600087518060c084015260005b818110156108dc576020818b0181015160e08684010152016108bf565b818111156108ee57600060e083860101525b5060208301889052601f01601f1916820160e0019050610916604083018763ffffffff169052565b63ffffffff8516606083015283608083015261093760a083018460ff169052565b979650505050505050565b600181811c9082168061095657607f821691505b6020821081141561097757634e487b7160e01b600052602260045260246000fd5b50919050565b600063ffffffff8083168185168083038211156109aa57634e487b7160e01b600052601160045260246000fd5b0194935050505056fea2646970667358221220dd8e1cb0ccb2e5d3bbee5672490e3eee1491f2f9bdcf460bd770125d0ae7882564736f6c634300080b0033"};

    public static final String BINARY = org.fisco.bcos.sdk.v3.utils.StringUtils.joinAll("", BINARY_ARRAY);

    public static final String[] SM_BINARY_ARRAY = {"608060405234801561001057600080fd5b506109ef806100206000396000f3fe608060405234801561001057600080fd5b50600436106100935760003560e01c806328bd05d31161006657806328bd05d31461011157806359cda3fe146100d35780636a392e6714610137578063acdd42fe1461014a578063ae823af01461018d57600080fd5b80630f390165146100985780631525ed7c146100ad5780631ea2a7bd146100c057806321a08ab0146100d3575b600080fd5b6100ab6100a636600461072c565b6101b2565b005b6100ab6100bb36600461072c565b61025d565b6100ab6100ce366004610797565b610352565b6100ab6100e13660046107ea565b600091825260026020526040909120805467ffffffffffffffff191667ffffffffffffffff909216919091179055565b61012461011f36600461072c565b6104bf565b6040519081526020015b60405180910390f35b6100ab610145366004610827565b6104eb565b61017461015836600461089b565b60026020526000908152604090205467ffffffffffffffff1681565b60405167ffffffffffffffff909116815260200161012e565b6101a061019b36600461089b565b6105c5565b60405161012e969594939291906108b4565b6000828152602081905260409020600481015460ff1660021461020d57604051636381e58960e11b815260206004820152600d60248201526c1b9bdd08195d985b1d585d1959609a1b60448201526064015b60405180910390fd5b60048101805460ff1916600317905560405183907fb816b03590cb6dacd4b7e3c5e38d67b0e91dbf51bba9d292575642d6b1dba4d1906102509085815260200190565b60405180910390a2505050565b6000828152602081905260409020600481015460ff166001146102b157604051636381e58960e11b815260206004820152600b60248201526a77726f6e6720737461746560a81b6044820152606401610204565b6002810154640100000000810463ffffffff90811691161461030857604051636381e58960e11b815260206004820152600f60248201526e6d697373696e67207265706f72747360881b6044820152606401610204565b6003810182905560048101805460ff1916600217905560405183907f4ca808217f89f93c6c975d9e93de86d1dd167228e1d3a2be5fe79054b54ce1be906102509085815260200190565b6000848152602081905260409020600481015460ff166001146103a957604051636381e58960e11b815260206004820152600e60248201526d6e6f7420636f6c6c656374696e6760901b6044820152606401610204565b6000858152600160209081526040808320878452909152902080546103cd90610948565b15905061040957604051636381e58960e11b81526020600482015260096024820152686475706c696361746560b81b6044820152606401610204565b6000858152600160209081526040808320878452909152902061042d908484610693565b5060018160020160048282829054906101000a900463ffffffff166104529190610983565b92506101000a81548163ffffffff021916908363ffffffff16021790555083857f4af005f4efd657f18c207343c29c834ccf97b269db913948e0e8f1d30dbfa165858590506040516104b0919063ffffffff91909116815260200190565b60405180910390a35050505050565b6000828152600160209081526040808320848452909152812080546104e390610948565b949350505050565b60008581526020819052604090206004015460ff161561053c57604051636381e58960e11b815260206004820152600b60248201526a7461736b2065786973747360a81b6044820152606401610204565b6000858152602081905260409020610555818686610693565b50600181810184905560028201805463ffffffff191663ffffffff851690811790915560048301805460ff191690921790915560405190815286907f5f8eabd610c77620b81106b37d4332c2df48e0a38c28a45d99c974b6cbb2bf509060200160405180910390a2505050505050565b6000602081905290815260409020805481906105e090610948565b80601f016020809104026020016040519081016040528092919081815260200182805461060c90610948565b80156106595780601f1061062e57610100808354040283529160200191610659565b820191906000526020600020905b81548152906001019060200180831161063c57829003601f168201915b5050506001840154600285015460038601546004909601549495919463ffffffff8083169550640100000000909204909116925060ff1686565b82805461069f90610948565b90600052602060002090601f0160209004810192826106c15760008555610707565b82601f106106da5782800160ff19823516178555610707565b82800160010185558215610707579182015b828111156107075782358255916020019190600101906106ec565b50610713929150610717565b5090565b5b808211156107135760008155600101610718565b6000806040838503121561073f57600080fd5b50508035926020909101359150565b60008083601f84011261076057600080fd5b50813567ffffffffffffffff81111561077857600080fd5b60208301915083602082850101111561079057600080fd5b9250929050565b600080600080606085870312156107ad57600080fd5b8435935060208501359250604085013567ffffffffffffffff8111156107d257600080fd5b6107de8782880161074e565b95989497509550505050565b600080604083850312156107fd57600080fd5b82359150602083013567ffffffffffffffff8116811461081c57600080fd5b809150509250929050565b60008060008060006080868803121561083f57600080fd5b85359450602086013567ffffffffffffffff81111561085d57600080fd5b6108698882890161074e565b90955093505060408601359150606086013563ffffffff8116811461088d57600080fd5b809150509295509295909350565b6000602082840312156108ad57600080fd5b5035919050565b60c08152600087518060c084015260005b818110156108e2576020818b0181015160e08684010152016108c5565b818111156108f457600060e083860101525b5060208301889052601f01601f1916820160e001905061091c604083018763ffffffff169052565b63ffffffff8516606083015283608083015261093d60a083018460ff169052565b979650505050505050565b600181811c9082168061095c57607f821691505b6020821081141561097d5763b95aa35560e01b600052602260045260246000fd5b50919050565b600063ffffffff8083168185168083038211156109b05763b95aa35560e01b600052601160045260246000fd5b0194935050505056fea264697066735822122030b4b4d2c0bf8c0f87bfdbb82cb315a31fe67486ee345af8b0f827bf1ff1d89764736f6c634300080b0033"};

    public static final String SM_BINARY = org.fisco.bcos.sdk.v3.utils.StringUtils.joinAll("", SM_BINARY_ARRAY);

    public static final String[] ABI_ARRAY = {"[{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"bytes32\",\"name\":\"qualityRoot\",\"type\":\"bytes32\"}],\"name\":\"QualitySubmitted\",\"type\":\"event\"},{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"uint32\",\"name\":\"bytesLength\",\"type\":\"uint32\"}],\"name\":\"ReportUploaded\",\"type\":\"event\"},{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"bytes32\",\"name\":\"paymentRoot\",\"type\":\"bytes32\"}],\"name\":\"Settled\",\"type\":\"event\"},{\"anonymous\":false,\"inputs\":[{\"indexed\":true,\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"indexed\":false,\"internalType\":\"uint32\",\"name\":\"expectedWorkers\",\"type\":\"uint32\"}],\"name\":\"TaskPublished\",\"type\":\"event\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes\",\"name\":\"encryptedTask\",\"type\":\"bytes\"},{\"internalType\":\"bytes32\",\"name\":\"locationTag\",\"type\":\"bytes32\"},{\"internalType\":\"uint32\",\"name\":\"expectedWorkers\",\"type\":\"uint32\"}],\"name\":\"publishTask\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"},{\"internalType\":\"uint64\",\"name\":\"initialReputation\",\"type\":\"uint64\"}],\"name\":\"registerWorker\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"}],\"name\":\"reportLength\",\"outputs\":[{\"internalType\":\"uint256\",\"name\":\"\",\"type\":\"uint256\"}],\"stateMutability\":\"view\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"\",\"type\":\"bytes32\"}],\"name\":\"reputation\",\"outputs\":[{\"internalType\":\"uint64\",\"name\":\"\",\"type\":\"uint64\"}],\"stateMutability\":\"view\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"paymentRoot\",\"type\":\"bytes32\"}],\"name\":\"settle\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"qualityRoot\",\"type\":\"bytes32\"}],\"name\":\"submitQuality\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"\",\"type\":\"bytes32\"}],\"name\":\"tasks\",\"outputs\":[{\"internalType\":\"bytes\",\"name\":\"encryptedTask\",\"type\":\"bytes\"},{\"internalType\":\"bytes32\",\"name\":\"locationTag\",\"type\":\"bytes32\"},{\"internalType\":\"uint32\",\"name\":\"expectedWorkers\",\"type\":\"uint32\"},{\"internalType\":\"uint32\",\"name\":\"reports\",\"type\":\"uint32\"},{\"internalType\":\"bytes32\",\"name\":\"qualityRoot\",\"type\":\"bytes32\"},{\"internalType\":\"uint8\",\"name\":\"state\",\"type\":\"uint8\"}],\"stateMutability\":\"view\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"},{\"internalType\":\"uint64\",\"name\":\"nextReputation\",\"type\":\"uint64\"}],\"name\":\"updateReputation\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"},{\"inputs\":[{\"internalType\":\"bytes32\",\"name\":\"taskId\",\"type\":\"bytes32\"},{\"internalType\":\"bytes32\",\"name\":\"workerTag\",\"type\":\"bytes32\"},{\"internalType\":\"bytes\",\"name\":\"ciphertext\",\"type\":\"bytes\"}],\"name\":\"uploadReport\",\"outputs\":[],\"stateMutability\":\"nonpayable\",\"type\":\"function\"}]"};

    public static final String ABI = org.fisco.bcos.sdk.v3.utils.StringUtils.joinAll("", ABI_ARRAY);

    public static final String FUNC_PUBLISHTASK = "publishTask";

    public static final String FUNC_REGISTERWORKER = "registerWorker";

    public static final String FUNC_REPORTLENGTH = "reportLength";

    public static final String FUNC_REPUTATION = "reputation";

    public static final String FUNC_SETTLE = "settle";

    public static final String FUNC_SUBMITQUALITY = "submitQuality";

    public static final String FUNC_TASKS = "tasks";

    public static final String FUNC_UPDATEREPUTATION = "updateReputation";

    public static final String FUNC_UPLOADREPORT = "uploadReport";

    public static final Event QUALITYSUBMITTED_EVENT = new Event("QualitySubmitted", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Bytes32>() {}));
    ;

    public static final Event REPORTUPLOADED_EVENT = new Event("ReportUploaded", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Bytes32>(true) {}, new TypeReference<Uint32>() {}));
    ;

    public static final Event SETTLED_EVENT = new Event("Settled", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Bytes32>() {}));
    ;

    public static final Event TASKPUBLISHED_EVENT = new Event("TaskPublished", 
            Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>(true) {}, new TypeReference<Uint32>() {}));
    ;

    protected BSIFWorkflow(String contractAddress, Client client, CryptoKeyPair credential) {
        super(getBinary(client.getCryptoSuite()), contractAddress, client, credential);
    }

    public static String getBinary(CryptoSuite cryptoSuite) {
        return (cryptoSuite.getCryptoTypeConfig() == CryptoType.ECDSA_TYPE ? BINARY : SM_BINARY);
    }

    public static String getABI() {
        return ABI;
    }

    public List<QualitySubmittedEventResponse> getQualitySubmittedEvents(
            TransactionReceipt transactionReceipt) {
        List<Contract.EventValuesWithLog> valueList = extractEventParametersWithLog(QUALITYSUBMITTED_EVENT, transactionReceipt);
        ArrayList<QualitySubmittedEventResponse> responses = new ArrayList<QualitySubmittedEventResponse>(valueList.size());
        for (Contract.EventValuesWithLog eventValues : valueList) {
            QualitySubmittedEventResponse typedResponse = new QualitySubmittedEventResponse();
            typedResponse.log = eventValues.getLog();
            typedResponse.taskId = (byte[]) eventValues.getIndexedValues().get(0).getValue();
            typedResponse.qualityRoot = (byte[]) eventValues.getNonIndexedValues().get(0).getValue();
            responses.add(typedResponse);
        }
        return responses;
    }

    public void subscribeQualitySubmittedEvent(BigInteger fromBlock, BigInteger toBlock,
            List<String> otherTopics, EventSubCallback callback) {
        String topic0 = eventEncoder.encode(QUALITYSUBMITTED_EVENT);
        subscribeEvent(topic0,otherTopics,fromBlock,toBlock,callback);
    }

    public void subscribeQualitySubmittedEvent(EventSubCallback callback) {
        String topic0 = eventEncoder.encode(QUALITYSUBMITTED_EVENT);
        subscribeEvent(topic0,callback);
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

    public TransactionReceipt publishTask(byte[] taskId, byte[] encryptedTask, byte[] locationTag,
            BigInteger expectedWorkers) {
        final Function function = new Function(
                FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(encryptedTask), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(locationTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint32(expectedWorkers)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodPublishTaskRawFunction(byte[] taskId, byte[] encryptedTask,
            byte[] locationTag, BigInteger expectedWorkers) throws ContractException {
        final Function function = new Function(FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(encryptedTask), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(locationTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint32(expectedWorkers)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForPublishTask(byte[] taskId, byte[] encryptedTask,
            byte[] locationTag, BigInteger expectedWorkers) {
        final Function function = new Function(
                FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(encryptedTask), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(locationTag), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Uint32(expectedWorkers)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String publishTask(byte[] taskId, byte[] encryptedTask, byte[] locationTag,
            BigInteger expectedWorkers, TransactionCallback callback) {
        final Function function = new Function(
                FUNC_PUBLISHTASK, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.DynamicBytes(encryptedTask), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(locationTag), 
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

    public TransactionReceipt submitQuality(byte[] taskId, byte[] qualityRoot) {
        final Function function = new Function(
                FUNC_SUBMITQUALITY, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(qualityRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return executeTransaction(function);
    }

    public Function getMethodSubmitQualityRawFunction(byte[] taskId, byte[] qualityRoot) throws
            ContractException {
        final Function function = new Function(FUNC_SUBMITQUALITY, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(qualityRoot)), 
                Arrays.<TypeReference<?>>asList());
        return function;
    }

    public String getSignedTransactionForSubmitQuality(byte[] taskId, byte[] qualityRoot) {
        final Function function = new Function(
                FUNC_SUBMITQUALITY, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(qualityRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return createSignedTransaction(function);
    }

    public String submitQuality(byte[] taskId, byte[] qualityRoot, TransactionCallback callback) {
        final Function function = new Function(
                FUNC_SUBMITQUALITY, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(taskId), 
                new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(qualityRoot)), 
                Collections.<TypeReference<?>>emptyList(), 0);
        return asyncExecuteTransaction(function, callback);
    }

    public Tuple2<byte[], byte[]> getSubmitQualityInput(TransactionReceipt transactionReceipt) {
        String data = transactionReceipt.getInput().substring(10);
        final Function function = new Function(FUNC_SUBMITQUALITY, 
                Arrays.<Type>asList(), 
                Arrays.<TypeReference<?>>asList(new TypeReference<Bytes32>() {}, new TypeReference<Bytes32>() {}));
        List<Type> results = this.functionReturnDecoder.decode(data, function.getOutputParameters());
        return new Tuple2<byte[], byte[]>(

                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue()
                );
    }

    public Tuple6<byte[], byte[], BigInteger, BigInteger, byte[], BigInteger> tasks(byte[] param0)
            throws ContractException {
        final Function function = new Function(FUNC_TASKS, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<DynamicBytes>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint8>() {}));
        List<Type> results = executeCallWithMultipleValueReturn(function);
        return new Tuple6<byte[], byte[], BigInteger, BigInteger, byte[], BigInteger>(
                (byte[]) results.get(0).getValue(), 
                (byte[]) results.get(1).getValue(), 
                (BigInteger) results.get(2).getValue(), 
                (BigInteger) results.get(3).getValue(), 
                (byte[]) results.get(4).getValue(), 
                (BigInteger) results.get(5).getValue());
    }

    public Function getMethodTasksRawFunction(byte[] param0) throws ContractException {
        final Function function = new Function(FUNC_TASKS, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<DynamicBytes>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint8>() {}));
        return function;
    }

    public void tasks(byte[] param0, CallCallback callback) throws ContractException {
        final Function function = new Function(FUNC_TASKS, 
                Arrays.<Type>asList(new org.fisco.bcos.sdk.v3.codec.datatypes.generated.Bytes32(param0)), 
                Arrays.<TypeReference<?>>asList(new TypeReference<DynamicBytes>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Uint32>() {}, new TypeReference<Bytes32>() {}, new TypeReference<Uint8>() {}));
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

    public static BSIFWorkflow load(String contractAddress, Client client,
            CryptoKeyPair credential) {
        return new BSIFWorkflow(contractAddress, client, credential);
    }

    public static BSIFWorkflow deploy(Client client, CryptoKeyPair credential) throws
            ContractException {
        return deploy(BSIFWorkflow.class, client, credential, getBinary(client.getCryptoSuite()), getABI(), null, null);
    }

    public static class QualitySubmittedEventResponse {
        public TransactionReceipt.Logs log;

        public byte[] taskId;

        public byte[] qualityRoot;
    }

    public static class ReportUploadedEventResponse {
        public TransactionReceipt.Logs log;

        public byte[] taskId;

        public byte[] workerTag;

        public BigInteger bytesLength;
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
}
