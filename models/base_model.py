import os
import torch


class BaseModel:

    # modify parser to add command line options,
    # and also change the default values if needed
    @staticmethod
    def modify_commandline_options(parser, is_train):
        return parser

    def name(self):
        return "BaseModel"

    def initialize(self, opts):
        self.opts = opts
        self.use_gpu = opts.model.use_gpu
        self.device = torch.device(
            "cuda" if (torch.cuda.is_available() and opts.model.use_gpu) else "cpu"
        )
        self.isTrain = opts.model.is_train
        self.loss_names = []
        self.model_names = []
        self.comet_exp = opts.comet_exp
        self.save_dir = opts.train.output_dir + "/checkpoints"

    def set_input(self, input):
        pass

    def forward(self):
        pass

    def validate(self):
        pass

    # load and print networks; create schedulers
    def setup(self):
        # TODO Resume training

        if not self.isTrain or self.opts.train.resume_checkpoint:
            load_suffix = self.opts.train.resume_ckpt_dir
            self.load_models(load_suffix)
        if not self.isTrain:
            self.eval()

        self.print_networks(self.opts.model.verbose)

    # make models eval mode during test time
    def eval(self):
        for name in self.model_names:
            if isinstance(name, str):
                net = getattr(self, "net" + name)
                net.eval()

    # used in test time, wrapping `forward` in no_grad() so we don't save
    # intermediate steps for backprop
    def test(self):
        with torch.no_grad():
            self.forward()

    def optimize_parameters(self):
        pass
    
    def resume(self):
        pass 
        
    # update learning rate (called once every epoch)
    def update_learning_rate(self):
        """
        for scheduler in self.schedulers:
            scheduler.step()
        lr = self.optimizers[0].param_groups[0]["lr"]
        print("learning rate = %.7f" % lr)
        """

    # return traning losses/errors.
    # train.py will print out these errors as debugging information
    def get_current_losses(self):
        print("get losses")
        """
        errors_ret = OrderedDict()
        for name in self.loss_names:
            if isinstance(name, str):
                # float(...) works for both scalar tensor and float number
                errors_ret[name] = float(getattr(self, "loss_" + name))
        return errors_ret
        """

    # save models to the disk
    def save_networks(self, epoch):
        print("save models")  # TODO: save checkpoints
        for name in self.model_names:
            if isinstance(name, str):
                save_filename = "%s_net_%s.pth" % (epoch, name)
                save_path = os.path.join(self.save_dir, save_filename)
                net = getattr(self, "net" + name)

                if self.use_gpu and torch.cuda.is_available():
                    torch.save(net.state_dict(), save_path)
                else:
                    torch.save(net.cpu().state_dict(), save_path)

    # load models from the disk
    def load_networks(self, epoch):

        for name in self.model_names:
            if isinstance(name, str):
                load_filename = "%s_net_%s.pth" % (epoch, name)
                load_path = os.path.join(self.save_dir, load_filename)
                net = getattr(self, "net" + name)
                if isinstance(net, torch.nn.DataParallel):
                    net = net.module
                print("loading the model from %s" % load_path)
                # if you are using PyTorch newer than 0.4 (e.g., built from
                # GitHub source), you can remove str() on self.device
                state_dict = torch.load(load_path, map_location=str(self.device))
                if hasattr(state_dict, "_metadata"):
                    del state_dict._metadata

                # patch InstanceNorm checkpoints prior to 0.4
                for key in list(
                    state_dict.keys()
                ):  # need to copy keys here because we mutate in loop
                    self.__patch_instance_norm_state_dict(
                        state_dict, net, key.split(".")
                    )
                net.load_state_dict(state_dict)

    # print network information
    def print_networks(self, verbose):
        print("---------- Networks initialized -------------")
        for name in self.model_names:
            if isinstance(name, str):
                net = getattr(self, "net" + name)
                num_params = 0
                for param in net.parameters():
                    num_params += param.numel()
                if verbose:
                    print(net)
                print(
                    "[Network %s] Total number of parameters : %.3f M"
                    % (name, num_params / 1e6)
                )
        print("-----------------------------------------------")

    # set requires_grad=False to avoid computation
    def set_requires_grad(self, nets, requires_grad=False):
        if not isinstance(nets, list):
            nets = [nets]
        for net in nets:
            if net is not None:
                for param in net.parameters():
                    param.requires_grad = requires_grad

    def __patch_instance_norm_state_dict(self, state_dict, module, keys, i=0):
        key = keys[i]
        if i + 1 == len(keys):  # at the end, pointing to a parameter/buffer
            if module.__class__.__name__.startswith("InstanceNorm") and (
                key == "running_mean" or key == "running_var"
            ):
                if getattr(module, key) is None:
                    state_dict.pop(".".join(keys))
            if module.__class__.__name__.startswith("InstanceNorm") and (
                key == "num_batches_tracked"
            ):
                state_dict.pop(".".join(keys))
        else:
            self.__patch_instance_norm_state_dict(
                state_dict, getattr(module, key), keys, i + 1
            )
    def save_models(self, epoch):
        print("save models")  # TODO: save checkpoints
        save_filename = "%s_maskgen.pth" % (epoch)
        save_path = os.path.join(self.save_dir, save_filename)
        save_dict = {}
        for name in self.model_names:
            if isinstance(name, str):
                save_dict["net_%s" % (name)] = getattr(self, "net" + name).state_dict()
                save_dict["optimizer_%s" % (name)] = getattr(
                    self, "optimizer_" + name
                ).state_dict()
        save_dict["epoch"] = epoch

        # if self.use_gpu and torch.cuda.is_available():
        torch.save(save_dict, save_path)
        # else:
        #    torch.save(save_dict.cpu().state_dict(), save_path)

    # load models from the disk
    def load_models(self, epoch):
        #load_filename = "%s_maskgen.pth" % (epoch)
        load_path = self.opts.train.resume_ckpt_dir#os.path.join(self.save_dir, load_filename)
        models = torch.load(load_path, map_location=str(self.device))
        for name in self.model_names:
            if isinstance(name, str):
                net = getattr(self, "net" + name)
                if isinstance(net, torch.nn.DataParallel):
                    net = net.module
                print("loading the model from %s" % load_path)
                state_dict = models["net_" + name]
                if hasattr(state_dict, "_metadata"):
                    del state_dict._metadata
                # patch InstanceNorm checkpoints prior to 0.4
                for key in list(
                    state_dict.keys()
                ):  # need to copy keys here because we mutate in loop
                    self.__patch_instance_norm_state_dict(
                        state_dict, net, key.split(".")
                    )
                net.load_state_dict(state_dict)

                opt = getattr(self, "optimizer_" + name)
                print("loading the optimizer from %s" % load_path)
                opt.load_state_dict(
                    models["optimizer_" + name]
                )